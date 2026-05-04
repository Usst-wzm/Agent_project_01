import datetime
import logging
import os
from encodings import utf_8

from utils.path_tool import get_abs_path

# 日志保存的根目录

LOG_ROOT = get_abs_path('logs')

# 确保日志的目录存在
os.makedirs(LOG_ROOT, exist_ok=True)

# 日志的格式配置
DEFAULT_LOG_FORMAT= logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d  - %(message)s')

def get_logger(
        name : str = "agent",
        console_level : int = logging.INFO,
        log_file : str = None,
        file_level : int = logging.DEBUG,
) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(console_level)

    # 避免重复添加
    if logger.handlers:
        return logger

    # 控制台日志
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(DEFAULT_LOG_FORMAT)
    logger.addHandler(console_handler)

    # 文件日志
    if not log_file:
        log_file = os.path.join(LOG_ROOT, datetime.datetime.now().strftime(f"{name}_%Y-%m-%d.log"))

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(file_level)
    file_handler.setFormatter(DEFAULT_LOG_FORMAT)

    logger.addHandler(file_handler)

    return  logger

# 快捷获取日志器

logger = get_logger()

if __name__ == '__main__':
    logger.info("消息日志")
    logger.error("错误日志")
    logger.debug("调试日志")
    logger.warning("警告日志")
