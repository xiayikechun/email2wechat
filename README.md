# Email2Wechat
通用 IMAP 邮箱新邮件实时监听，自动转发至企业微信自建应用。
支持 IMAP IDLE 长连接、异常自动重连、环境变量 / 挂载配置双模式。

## 功能特性
- 支持所有开启 IMAP SSL(993) + IDLE 协议的邮箱
- 新邮件秒级推送，无轮询延迟
- 自动解析标题 + 正文，超长自动截断
- 企业微信 Token 本地缓存
- 掉线自动重连，稳定后台运行
- 环境变量 / config.py 双模式部署
- GitHub Actions 自动构建 Docker 镜像

## 支持邮箱列表
阿里云企业邮箱、腾讯企业邮箱、QQ邮箱、163、Outlook、Gmail、自建邮件系统等。

## 常用邮箱 IMAP 速查
### 阿里云企业邮箱
IMAP_SERVER=imap.qiye.aliyun.com
FOLDER_NAME=收件箱

### 腾讯企业邮箱
IMAP_SERVER=imap.exmail.qq.com
FOLDER_NAME=INBOX

### QQ 个人邮箱
IMAP_SERVER=imap.qq.com
FOLDER_NAME=INBOX

### 163邮箱
 
IMAP_SERVER=imap.163.com
FOLDER_NAME=INBOX
 
### Outlook
 
IMAP_SERVER=imap-mail.outlook.com
FOLDER_NAME=INBOX
 

### Gmail
 
IMAP_SERVER=imap.gmail.com
FOLDER_NAME=INBOX


## 部署方式（二选一）

### 方式一：环境变量（推荐）
```bash
docker run -d \
  --restart always \
  --name email2wechat \
  -e IMAP_SERVER="imap.xxx.com" \
  -e USERNAME="your@email.com" \
  -e PASSWORD="password_or_auth_code" \
  -e FOLDER_NAME="INBOX" \
  -e WECHAT_CORPID="wwxxxx" \
  -e WECHAT_CORPSECRET="xxxx" \
  -e WECHAT_AGENTID=1000001 \
  xiayikechun/email2wechat:latest

方式二：挂载 config.py
docker run -d \
  --restart always \
  --name email2wechat \
  -v ./config.py:/app/config.py \
  xiayikechun/email2wechat:latest
  
环境变量说明

IMAP_SERVER        IMAP 服务器
IMAP_PORT          端口默认 993
USERNAME           邮箱账号
PASSWORD           密码/授权码
FOLDER_NAME        文件夹
WECHAT_CORPID      企业微信 CorpID
WECHAT_CORPSECRET  应用 Secret
WECHAT_AGENTID     应用 AgentId
LOG_LEVEL          日志级别

运维命令

docker logs -f email2wechat
docker restart email2wechat
docker pull xiayikechun/email2wechat:latest


常见问题
 
- 404/60021：CorpID/Secret/AgentID 错误
​
- 登录失败：未开 IMAP 或用了登录密码而非授权码
​
- 收不到提醒：文件夹名错误、邮箱不支持 IDLE