# This must be the first to import
from module.base.logger import logger  # Change folder
import deploy.Windows.logger

deploy.Windows.logger.logger = logger
