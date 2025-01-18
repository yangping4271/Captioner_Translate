import logging
import logging.handlers
from pathlib import Path

# 路径
ROOT_PATH = Path(__file__).parent.parent
LOG_PATH = ROOT_PATH / "logs"

# 日志配置
LOG_LEVEL = logging.INFO

def setup_logger(name: str, 
                level: int = LOG_LEVEL,
                log_fmt: str = '%(asctime)s - %(message)s',
                datefmt: str = '%Y-%m-%d %H:%M:%S',
                log_file: str = str(LOG_PATH / 'app.log')) -> logging.Logger:
    """
    创建并配置一个日志记录器。

    参数：
    - name: 日志记录器的名称
    - level: 日志级别
    - log_fmt: 日志格式字符串
    - datefmt: 时间格式字符串
    - log_file: 日志文件路径
    """
    
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        formatter = logging.Formatter(log_fmt, datefmt=datefmt)

        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # 文件处理器
        if log_file:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

    # 设置特定库的日志级别为ERROR以减少日志噪音
    error_loggers = ["urllib3", "requests", "openai", "httpx", "httpcore", "ssl", "certifi"]
    for lib in error_loggers:
        logging.getLogger(lib).setLevel(logging.ERROR)

    return logger