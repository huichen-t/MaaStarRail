"""
通知系统模块，提供统一的消息推送接口。
支持多种推送渠道，包括但不限于：
- 钉钉
- 企业微信
- 飞书
- 自定义HTTP请求
- 其他OnePush支持的渠道
"""

import onepush.core
import yaml
from onepush import get_notifier
from onepush.core import Provider
from onepush.exceptions import OnePushException
from onepush.providers.custom import Custom
from requests import Response

from module.base.logger import logger

# 使用项目的logger替换onepush的logger
onepush.core.log = logger


def handle_notify(_config: str, **kwargs) -> bool:
    """
    处理通知发送请求。
    
    工作流程：
    1. 解析通知配置
    2. 获取通知提供者
    3. 验证必要参数
    4. 发送通知
    5. 处理响应结果
    
    Args:
        _config (str): YAML格式的通知配置字符串，包含provider和其他必要参数
        **kwargs: 其他通知参数，如title和content
    
    Returns:
        bool: 通知是否发送成功
    
    配置示例：
    ```yaml
    provider: dingtalk
    token: your_token
    secret: your_secret
    ```
    """
    try:
        # 解析YAML配置
        config = {}
        for item in yaml.safe_load_all(_config):
            config.update(item)
    except Exception:
        logger.error("Fail to load onepush config_src, skip sending")
        return False
        
    try:
        # 获取通知提供者
        provider_name: str = config.pop("provider", None)
        if provider_name is None:
            logger.info("No provider specified, skip sending")
            return False
        notifier: Provider = get_notifier(provider_name)
        
        # 获取必要参数列表
        required: list[str] = notifier.params["required"]
        # 合并配置和额外参数
        config.update(kwargs)

        # 预检查必要参数
        for key in required:
            if key not in config:
                logger.warning(
                    f"Notifier {notifier.name} require param '{key}' but not provided"
                )

        # 处理自定义HTTP请求
        if isinstance(notifier, Custom):
            # 设置默认数据格式为JSON
            if "method" not in config or config["method"] == "post":
                config["datatype"] = "json"
            # 确保data字段存在且为字典类型
            if not ("data" in config or isinstance(config["data"], dict)):
                config["data"] = {}
            # 将title和content添加到data中
            if "title" in kwargs:
                config["data"]["title"] = kwargs["title"]
            if "content" in kwargs:
                config["data"]["content"] = kwargs["content"]

        # 特殊处理GoCqHttp
        if provider_name.lower() == "gocqhttp":
            access_token = config.get("access_token")
            if access_token:
                config["token"] = access_token

        # 发送通知
        resp = notifier.notify(**config)
        
        # 处理响应
        if isinstance(resp, Response):
            if resp.status_code != 200:
                logger.warning("Push notify failed!")
                logger.warning(f"HTTP Code:{resp.status_code}")
                return False
            else:
                # 特殊处理GoCqHttp的响应
                if provider_name.lower() == "gocqhttp":
                    return_data: dict = resp.json()
                    if return_data["status"] == "failed":
                        logger.warning("Push notify failed!")
                        logger.warning(
                            f"Return message:{return_data['wording']}")
                        return False
    except OnePushException:
        logger.exception("Push notify failed")
        return False
    except Exception as e:
        logger.exception(e)
        return False

    logger.info("Push notify success")
    return True