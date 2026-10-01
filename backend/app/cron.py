import logging

logger = logging.getLogger("cron")


def update_access_token():
    """保留旧 Cron 入口兼容；Claude 网页 sessionKey 不支持自动刷新。"""
    logger.info("已跳过旧上游令牌刷新：Claude 网页会话需由网关诊断")


def check_access_token():
    """保留旧 Cron 入口兼容；不能以 JWT exp 判定 Claude sessionKey。"""
    logger.info("已跳过旧上游令牌过期检查：Claude sessionKey 的到期时间未知")
