import logging
import sys
import colorlog

def setup_logging():

    log_colors = {
        'DEBUG':    'cyan',
        'INFO':     'green',        #
        'WARNING':  'yellow',       
        'ERROR':    'red',          
        'CRITICAL': 'red,bg_white', # Lỗi chí mạng có chữ đỏ nền trắng
    }

    # Định dạng hiển thị log cho Terminal
    terminal_format = "%(log_color)s%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    
    # Định dạng hiển thị log khi ghi vào file 
    file_format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"

    color_formatter = colorlog.ColoredFormatter(
        terminal_format,
        log_colors=log_colors,
        reset=True,
        style='%'
    )

    # In log ra màn hình Terminal
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(color_formatter)

    # Lưu log vào file app.log (Text thuần, không màu)
    file_handler = logging.FileHandler("app.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(file_format))

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    root_logger.handlers = []
    
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)

    # Giảm bớt các log rác, log quét từ uvicorn
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("watchfiles.main").setLevel(logging.WARNING)
    logging.getLogger("watchfiles").setLevel(logging.WARNING)