import redis
import logging

from config.settings_config import settings

logger = logging.getLogger(__name__)

redis_client = redis.Redis(
    host = settings.REDIS_HOST,  
    port = settings.REDIS_PORT, 
    db = 0, 
    decode_responses = True
)