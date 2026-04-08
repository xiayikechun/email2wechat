# -*- coding: utf-8 -*-
import imaplib
import time
import email
import requests
import socket
import logging
import logging.handlers
import json
import os
from email.header import decode_header
from imapclient import imap_utf7

# ========== 配置加载：环境变量优先，兼容 config.py ==========
try:
    import config
except ImportError:
    config = None

def get_conf(key, default=''):
    env_key = key.upper()
    val = os.getenv(env_key)
    if val is not None:
        return val
    if config is not None and hasattr(config, key):
        return getattr(config, key)
    return default

# ========== 实际生效配置 ==========
IMAP_SERVER       = get_conf('IMAP_SERVER')
IMAP_PORT         = int(get_conf('IMAP_PORT', 993))
USERNAME          = get_conf('USERNAME')
PASSWORD          = get_conf('PASSWORD')
FOLDER_NAME       = get_conf('FOLDER_NAME', 'INBOX')

WECHAT_CORPID     = get_conf('WECHAT_CORPID')
WECHAT_CORPSECRET = get_conf('WECHAT_CORPSECRET')
WECHAT_AGENTID    = int(get_conf('WECHAT_AGENTID', 1000001))

LOG_FILE          = get_conf('LOG_FILE', 'email_webhook.log')
LOG_LEVEL         = get_conf('LOG_LEVEL', 'INFO')
LOG_MAX_BYTES     = int(get_conf('LOG_MAX_BYTES', 10*1024*1024))
LOG_BACKUP_COUNT  = int(get_conf('LOG_BACKUP_COUNT', 5))

# ========== 日志 ==========
def setup_logging():
    logger = logging.getLogger()
    log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(log_level)
    if logger.handlers:
        return logger

    fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    try:
        file_handler = logging.RotatingFileHandler(
            LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding='utf-8'
        )
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"日志文件不可写: {e}")

    return logger

logger = setup_logging()

# ========== 企业微信 Token ==========
TOKEN_FILE = 'wechat_token.txt'

def get_access_token():
    now = time.time()
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                token = data.get('token')
                expire_at = data.get('expire_at', 0)
                if token and expire_at > now:
                    return token
        except Exception:
            pass

    url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={WECHAT_CORPID}&corpsecret={WECHAT_CORPSECRET}"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get('errcode') != 0:
            logger.error(f"获取token失败: {data}")
            return None
        token = data['access_token']
        expire_at = now + data.get('expires_in', 7200) - 200
        with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
            json.dump({'token': token, 'expire_at': expire_at}, f)
        return token
    except Exception as e:
        logger.error(f"请求token异常: {e}")
        return None

def send_wechat_msg(subject, body):
    token = get_access_token()
    if not token:
        return

    content = f"📩 新邮件通知\n主题：{subject}\n\n{body}"
    if len(content.encode('utf-8')) > 2048:
        content = content[:2000] + "\n...(内容过长已截断)"

    payload = {
        "touser": "@all",
        "msgtype": "text",
        "agentid": WECHAT_AGENTID,
        "text": {"content": content},
        "safe": 0
    }

    url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
    try:
        r = requests.post(url, json=payload, timeout=10)
        j = r.json()
        if j.get('errcode') == 0:
            logger.info(f"推送成功：{subject[:60]}")
        else:
            logger.error(f"推送失败：{j}")
    except Exception as e:
        logger.error(f"推送异常：{e}")

# ========== 邮件解析 ==========
def decode_str(s):
    if not s:
        return ''
    parts = decode_header(s)
    res = ''
    for part, enc in parts:
        if isinstance(part, bytes):
            try:
                res += part.decode(enc or 'utf-8', errors='replace')
            except:
                res += part.decode('utf-8', errors='replace')
        else:
            res += str(part)
    return res.strip()

def get_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition", ""))
            if ctype == "text/plain" and "attachment" not in disp:
                b = part.get_payload(decode=True)
                enc = part.get_content_charset() or 'utf-8'
                return b.decode(enc, errors='replace')
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                b = part.get_payload(decode=True)
                enc = part.get_content_charset() or 'utf-8'
                return b.decode(enc, errors='replace')
    else:
        b = msg.get_payload(decode=True)
        enc = msg.get_content_charset() or 'utf-8'
        return b.decode(enc, errors='replace')
    return ""

# ========== 未读邮件处理 ==========
def process_unseen(mail):
    try:
        typ, data = mail.search(None, 'UNSEEN')
        if typ != 'OK':
            return
        ids = data[0].split()
        if not ids:
            logger.info("暂无新邮件")
            return
        logger.info(f"发现 {len(ids)} 封未读邮件")
        for mid in ids:
            typ, d = mail.fetch(mid, '(RFC822)')
            if typ != 'OK':
                continue
            msg = email.message_from_bytes(d[0][1])
            subject = decode_str(msg.get('Subject', '无主题'))
            body = get_body(msg)
            send_wechat_msg(subject, body)
            mail.store(mid, '+FLAGS', '\\Seen')
    except Exception as e:
        logger.exception("处理邮件出错")

# ========== IDLE 监听 ==========
def idle_loop(mail):
    mail.socket().settimeout(300)
    mail.send(b'a001 IDLE\r\n')
    while True:
        try:
            line = mail.readline()
            if not line:
                return
            if b'EXISTS' in line:
                mail.send(b'DONE\r\n')
                while True:
                    r = mail.readline()
                    if not r or r.startswith(b'a001 '):
                        break
                process_unseen(mail)
                mail.send(b'a001 IDLE\r\n')
        except socket.timeout:
            continue
        except Exception as e:
            raise

# ========== 主循环 + 自动重连 ==========
def main():
    while True:
        try:
            if not IMAP_SERVER or not USERNAME or not PASSWORD:
                logger.error("请配置 IMAP_SERVER、USERNAME、PASSWORD")
                time.sleep(30)
                continue
            logger.info(f"正在连接 {IMAP_SERVER}:{IMAP_PORT} ...")
            mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
            mail.login(USERNAME, PASSWORD)
            folder = imap_utf7.encode(FOLDER_NAME)
            mail.select(folder)
            logger.info(f"已进入文件夹：{FOLDER_NAME}，开始监听")
            process_unseen(mail)
            idle_loop(mail)
        except Exception as e:
            logger.info(f"连接断开，5秒后重连：{str(e)[:100]}")
            time.sleep(5)

if __name__ == '__main__':
    main()
