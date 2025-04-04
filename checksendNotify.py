#!/usr/bin/env python3
# _*_ coding:utf-8 _*_
import base64
import hashlib
import hmac
import json
import os
import re
import threading
import time
import traceback
import urllib.parse

import requests
import tomli

# 原先的 print 函数和主线程的锁
_print = print
mutex = threading.Lock()


# 定义新的 print 函数
def print(text, *args, **kw):
    """
    使输出有序进行，不出现多线程同一时间输出导致错乱的问题。
    """
    with mutex:
        _print(text, *args, **kw)


# 通知服务
# fmt: off
push_config = {
    'HITOKOTO': False,  # 启用一言（随机句子）

    'BARK_PUSH': '',  # bark IP 或设备码，例：https://api.day.app/DxHcxxxxxRxxxxxxcm
    'BARK_ARCHIVE': '',  # bark 推送是否存档
    'BARK_GROUP': '',  # bark 推送分组
    'BARK_SOUND': '',  # bark 推送声音

    'CONSOLE': True,  # 控制台输出

    'DD_BOT_SECRET': '',  # 钉钉机器人的 DD_BOT_SECRET
    'DD_BOT_TOKEN': '',  # 钉钉机器人的 DD_BOT_TOKEN

    'FSKEY': '',  # 飞书机器人的 FSKEY

    'GOBOT_URL': '',  # go-cqhttp
    # 推送到个人QQ：http://127.0.0.1/send_private_msg
    # 群：http://127.0.0.1/send_group_msg
    'GOBOT_QQ': '',  # go-cqhttp 的推送群或用户
    # GOBOT_URL 设置 /send_private_msg 时填入 user_id=个人QQ
    #               /send_group_msg   时填入 group_id=QQ群
    'GOBOT_TOKEN': '',  # go-cqhttp 的 access_token

    'IGOT_PUSH_KEY': '',  # iGot 聚合推送的 IGOT_PUSH_KEY

    'PUSH_KEY': '',  # server 酱的 PUSH_KEY，兼容旧版与 Turbo 版

    'PUSH_PLUS_TOKEN': '',  # push+ 微信推送的用户令牌
    'PUSH_PLUS_USER': '',  # push+ 微信推送的群组编码

    'QMSG_KEY': '',  # qmsg 酱的 QMSG_KEY
    'QMSG_TYPE': '',  # qmsg 酱的 QMSG_TYPE

    'QYWX_AM': '',  # 企业微信应用

    'QYWX_KEY': '',  # 企业微信机器人

    'TG_BOT_TOKEN': '',  # tg 机器人的 TG_BOT_TOKEN，例：1407203283:AAG9rt-6RDaaX0HBLZQq0laNOh898iFYaRQ
    'TG_USER_ID': '',  # tg 机器人的 TG_USER_ID，例：1434078534
    'TG_API_HOST': '',  # tg 代理 api
    'TG_PROXY_AUTH': '',  # tg 代理认证参数
    'TG_PROXY_HOST': '',  # tg 机器人的 TG_PROXY_HOST
    'TG_PROXY_PORT': '',  # tg 机器人的 TG_PROXY_PORT
    'MI_PUSH_ALIAS': '',
}
notify_function = []
# fmt: on

# 首先读取 面板变量 或者 github action 运行变量
for k in push_config:
    if v := os.getenv(k):
        push_config[k] = v


# 读取配置文件中的变量 (会覆盖环境变量)
# CONFIG_PATH = os.getenv("NOTIFY_CONFIG_PATH")
# if os.path.exists(CONFIG_PATH):
#     print(f"通知配置文件存在：{CONFIG_PATH}。")
#     try:
#         for k, v in dict(tomli.load(open(CONFIG_PATH, "rb"))).items():
#             if k in push_config:
#                 push_config[k] = v
#     except tomli.TOMLDecodeError:
#         print(
#             f"错误：配置文件 {CONFIG_PATH} 格式不对，请学习 https://toml.io/cn/v1.0.0\n错误信息：\n{traceback.format_exc()}"
#         )
# elif CONFIG_PATH:
#     print(f"{CONFIG_PATH} 配置的通知文件不存在，请检查文件位置或删除对应环境变量！")


def bark(title: str, content: str) -> None:
    """
    使用 bark 推送消息。
    """
    if not push_config.get("BARK_PUSH"):
        print("bark 服务的 BARK_PUSH 未设置!!\n取消推送")
        return
    print("bark 服务启动")

    if push_config.get("BARK_PUSH").startswith("http"):
        url = f'{push_config.get("BARK_PUSH").rstrip("/")}/{urllib.parse.quote_plus(title)}/{urllib.parse.quote_plus(content)}'
    else:
        url = f'https://api.day.app/{push_config.get("BARK_PUSH")}/{urllib.parse.quote_plus(title)}/{urllib.parse.quote_plus(content)}'

    bark_params = {
        "BARK_ARCHIVE": "isArchive",
        "BARK_GROUP": "group",
        "BARK_SOUND": "sound",
    }
    params = ""
    for pair in filter(
            lambda pairs: pairs[0].startswith("BARK_")
                          and pairs[0] != "BARK_PUSH"
                          and pairs[1]
                          and bark_params.get(pairs[0]),
            push_config.items(),
    ):
        params += f"{bark_params.get(pair[0])}={pair[1]}&"
    if params:
        url = url + "?" + params.rstrip("&")

    datas = requests.get(url, timeout=15).json()
    if datas.get("code") == 200:
        print("bark 推送成功！")
    elif datas.get("code") == 400:
        print("bark 推送失败！找不到 Key 对应的 DeviceToken。")
    else:
        print(f"bark 推送失败！响应数据：{datas}")


def console(title: str, content: str) -> None:
    """
    使用 控制台 推送消息。
    """
    print(f"{title}\n\n{content}")


def dingding_bot(title: str, content: str) -> None:
    """
    使用 钉钉机器人 推送消息。
    """
    if not push_config.get("DD_BOT_SECRET") or not push_config.get("DD_BOT_TOKEN"):
        print("钉钉机器人 服务的 DD_BOT_SECRET 或者 DD_BOT_TOKEN 未设置!!\n取消推送")
        return
    print("钉钉机器人 服务启动")

    timestamp = str(round(time.time() * 1000))
    secret_enc = push_config.get("DD_BOT_SECRET").encode("utf-8")
    string_to_sign = "{}\n{}".format(timestamp, push_config.get("DD_BOT_SECRET"))
    string_to_sign_enc = string_to_sign.encode("utf-8")
    hmac_code = hmac.new(
        secret_enc, string_to_sign_enc, digestmod=hashlib.sha256
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    url = f'https://oapi.dingtalk.com/robot/send?access_token={push_config.get("DD_BOT_TOKEN")}&timestamp={timestamp}&sign={sign}'
    headers = {"Content-Type": "application/json;charset=utf-8"}
    data = {"msgtype": "text", "text": {"content": f"{title}\n\n{content}"}}

    datas = requests.post(
        url=url, data=json.dumps(data), headers=headers, timeout=15
    ).json()
    if datas.get("errcode") == 0:
        print("钉钉机器人 推送成功！")
    else:
        print(f"钉钉机器人 推送失败！响应数据：{datas}")


def feishu_bot(title: str, content: str) -> None:
    """
    使用 飞书机器人 推送消息。
    """
    if not push_config.get("FSKEY"):
        print("飞书 服务的 FSKEY 未设置!!\n取消推送")
        return
    print("飞书 服务启动")

    url = f'https://open.feishu.cn/open-apis/bot/v2/hook/{push_config.get("FSKEY")}'
    data = {"msg_type": "text", "content": {"text": f"{title}\n\n{content}"}}

    datas = requests.post(url, data=json.dumps(data), timeout=15)
    datas = datas.json
    if datas.get("StatusCode") == 0:
        print("飞书 推送成功！")
    else:
        print(f"飞书 推送失败！响应数据：{datas}")


def go_cqhttp(title: str, content: str) -> None:
    """
    使用 go_cqhttp 推送消息。
    """
    if not push_config.get("GOBOT_URL") or not push_config.get("GOBOT_QQ"):
        print("go-cqhttp 服务的 GOBOT_URL 或 GOBOT_QQ 未设置!!\n取消推送")
        return
    print("go-cqhttp 服务启动")

    url = f'{push_config.get("GOBOT_URL")}?access_token={push_config.get("GOBOT_TOKEN")}&{push_config.get("GOBOT_QQ")}&message=标题:{title}\n内容:{content}'

    datas = requests.get(url, timeout=15).json()
    if datas.get("status") == "ok":
        print("go-cqhttp 推送成功！")
    else:
        print(f"go-cqhttp 推送失败！响应数据：{datas}")


def iGot(title: str, content: str) -> None:
    """
    使用 iGot 推送消息。
    """
    if not push_config.get("IGOT_PUSH_KEY"):
        print("iGot 服务的 IGOT_PUSH_KEY 未设置!!\n取消推送")
        return
    print("iGot 服务启动")

    url = f'https://push.hellyw.com/{push_config.get("IGOT_PUSH_KEY")}'
    data = {"title": title, "content": content}
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    datas = requests.post(url, data=data, headers=headers, timeout=15).json()
    if datas.get("ret") == 0:
        print("iGot 推送成功！")
    else:
        print(f'iGot 推送失败！错误信息：{datas.get("errMsg")}')


def serverJ(title: str, content: str) -> None:
    """
    通过 serverJ 推送消息。
    """
    if not push_config.get("PUSH_KEY"):
        print("serverJ 服务的 PUSH_KEY 未设置!!\n取消推送")
        return
    print("serverJ 服务启动")

    data = {"text": title, "desp": content.replace("\n", "\n\n")}
    if push_config.get("PUSH_KEY").index("SCT") != -1:
        url = f'https://sctapi.ftqq.com/{push_config.get("PUSH_KEY")}.send'
    else:
        url = f'https://sc.ftqq.com/${push_config.get("PUSH_KEY")}.send'

    datas = requests.post(url, data=data, timeout=15).json()
    if datas.get("errno") == 0 or datas.get("code") == 0:
        print("serverJ 推送成功！")
    elif datas.get("code") == 40001:
        print("serverJ 推送失败！PUSH_KEY 错误。")
    else:
        print(f'serverJ 推送失败！错误码：{datas.get("message")}')


def pushplus_bot(title: str, content: str) -> None:
    """
    通过 push+ 推送消息。
    """
    if not push_config.get("PUSH_PLUS_TOKEN"):
        print("PUSHPLUS 服务的 PUSH_PLUS_TOKEN 未设置!!\n取消推送")
        return
    print("PUSHPLUS 服务启动")

    url = "http://www.pushplus.plus/send"
    data = {
        "token": push_config.get("PUSH_PLUS_TOKEN"),
        "title": title,
        "content": content,
        "topic": push_config.get("PUSH_PLUS_USER"),
    }
    body = json.dumps(data).encode(encoding="utf-8")
    headers = {"Content-Type": "application/json"}

    datas = requests.post(url=url, data=body, headers=headers, timeout=15).json()
    if datas.get("code") == 200:
        print("PUSHPLUS 推送成功！")
    elif datas.get("code") == 600:
        url2 = "http://pushplus.hxtrip.com/send"
        headers["Accept"] = "application/json"
        datas2 = requests.post(url=url2, data=body, headers=headers, timeout=15).json()
        if datas2.get("code") == 200:
            print("PUSHPLUS(hxtrip) 推送成功！")
        elif datas2.get("code") == 600:
            print("PUSHPLUS 推送失败！PUSH_PLUS_TOKEN 错误。")
        else:
            print(f"PUSHPLUS(hxtrip) 推送失败！响应数据：{datas2}")
    else:
        print(f"PUSHPLUS 推送失败！响应数据：{datas}")


def qmsg_bot(title: str, content: str) -> None:
    """
    使用 qmsg 推送消息。
    """
    if not push_config.get("QMSG_KEY") or not push_config.get("QMSG_TYPE"):
        print("qmsg 的 QMSG_KEY 或者 QMSG_TYPE 未设置!!\n取消推送")
        return
    print("qmsg 服务启动")

    url = f'https://qmsg.zendee.cn/{push_config.get("QMSG_TYPE")}/{push_config.get("QMSG_KEY")}'
    payload = {"msg": f'{title}\n\n{content.replace("----", "-")}'.encode("utf-8")}

    datas = requests.post(url=url, params=payload, timeout=15).json()
    if datas.get("code") == 0:
        print("qmsg 推送成功！")
    else:
        print(f'qmsg 推送失败！错误信息：{datas.get("reason")}')


def mi_push(title: str, content: str) -> None:
    """
    使用来自消息接收APP的推送服务
    """
    if not push_config.get("MI_PUSH_ALIAS"):
        print("MI_PUSH_ALIAS 未设置!!\n取消推送")
    url = "http://tdtt.top"
    data = {"title": title, "content": content, "alias": push_config.get("MI_PUSH_ALIAS")}
    datas = requests.post(url=url, data=data)
    print(f"失败 {datas}") if not datas.status_code == requests.codes.ok else print('MI_PUSH推送成功')
    return


def wecom_app(title: str, content: str) -> None:
    """
    通过 企业微信 APP 推送消息。
    """
    if not push_config.get("QYWX_AM"):
        print("QYWX_AM 未设置!!\n取消推送")
        return
    QYWX_AM_AY = re.split(",", push_config.get("QYWX_AM"))
    if 4 < len(QYWX_AM_AY) > 5:
        print("QYWX_AM 设置错误!!\n取消推送")
        return
    print("企业微信 APP 服务启动")

    corpid = QYWX_AM_AY[0]
    corpsecret = QYWX_AM_AY[1]
    touser = QYWX_AM_AY[2]
    agentid = QYWX_AM_AY[3]
    try:
        media_id = QYWX_AM_AY[4]
    except IndexError:
        media_id = ""
    wx = WeCom(corpid, corpsecret, agentid)
    # 如果没有配置 media_id 默认就以 text 方式发送
    if not media_id:
        message = title + "\n\n" + content
        datas = wx.send_text(message, touser)
    else:
        datas = wx.send_mpnews(title, content, media_id, touser)
    if datas == "ok":
        print("企业微信推送成功！")
    else:
        print(f"企业微信推送失败！错误信息：{datas}")


class WeCom:
    def __init__(self, corpid, corpsecret, agentid):
        self.CORPID = corpid
        self.CORPSECRET = corpsecret
        self.AGENTID = agentid

    def get_access_token(self):
        url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
        values = {
            "corpid": self.CORPID,
            "corpsecret": self.CORPSECRET,
        }
        req = requests.post(url, params=values, timeout=15)
        datas = json.loads(req.text)
        return datas.get("access_token")

    def send_text(self, message, touser="@all"):
        send_url = (
                "https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token="
                + self.get_access_token()
        )
        send_values = {
            "touser": touser,
            "msgtype": "text",
            "agentid": self.AGENTID,
            "text": {"content": message},
            "safe": "0",
        }
        send_msges = bytes(json.dumps(send_values), "utf-8")
        datas = requests.post(send_url, send_msges, timeout=15).json()
        return datas.get("errmsg")

    def send_mpnews(self, title, message, media_id, touser="@all"):
        send_url = (
                "https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token="
                + self.get_access_token()
        )
        send_values = {
            "touser": touser,
            "msgtype": "mpnews",
            "agentid": self.AGENTID,
            "mpnews": {
                "articles": [
                    {
                        "title": title,
                        "thumb_media_id": media_id,
                        "author": "Author",
                        "content_source_url": "",
                        "content": message.replace("\n", "<br/>"),
                        "digest": message,
                    }
                ]
            },
        }
        send_msges = bytes(json.dumps(send_values), "utf-8")
        datas = requests.post(send_url, send_msges, timeout=15).json()
        return datas.get("errmsg")


def wecom_bot(title: str, content: str) -> None:
    """
    通过 企业微信机器人 推送消息。
    """
    if not push_config.get("QYWX_KEY"):
        print("企业微信机器人 服务的 QYWX_KEY 未设置!!\n取消推送")
        return
    print("企业微信机器人服务启动")

    url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={push_config.get('QYWX_KEY')}"
    headers = {"Content-Type": "application/json;charset=utf-8"}
    data = {"msgtype": "text", "text": {"content": f"{title}\n\n{content}"}}

    datas = requests.post(
        url=url, data=json.dumps(data), headers=headers, timeout=15
    ).json()
    if datas.get("errcode") == 0:
        print("企业微信机器人 推送成功！")
    else:
        print(f"企业微信机器人 推送失败！响应数据：{datas}")


def telegram_bot(title: str, content: str) -> None:
    """
    使用 telegram 机器人 推送消息。
    """
    if not push_config.get("TG_BOT_TOKEN") or not push_config.get("TG_USER_ID"):
        print("tg 服务的 bot_token 或者 user_id 未设置!!\n取消推送")
        return
    print("tg 服务启动")

    if push_config.get("TG_API_HOST"):
        url = f"https://{push_config.get('TG_API_HOST')}/bot{push_config.get('TG_BOT_TOKEN')}/sendMessage"
    else:
        url = (
            f"https://api.telegram.org/bot{push_config.get('TG_BOT_TOKEN')}/sendMessage"
        )
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload = {
        "chat_id": str(push_config.get("TG_USER_ID")),
        "text": f"{title}\n\n{content}",
        "disable_web_page_preview": "true",
    }
    proxies = None
    if push_config.get("TG_PROXY_HOST") and push_config.get("TG_PROXY_PORT"):
        if push_config.get("TG_PROXY_AUTH") is not None and "@" not in push_config.get(
                "TG_PROXY_HOST"
        ):
            push_config["TG_PROXY_HOST"] = (
                    push_config.get("TG_PROXY_AUTH")
                    + "@"
                    + push_config.get("TG_PROXY_HOST")
            )
        proxyStr = "http://{}:{}".format(
            push_config.get("TG_PROXY_HOST"), push_config.get("TG_PROXY_PORT")
        )
        proxies = {"http": proxyStr, "https": proxyStr}

    datas = requests.post(
        url=url, headers=headers, params=payload, proxies=proxies, timeout=15
    ).json()
    if datas.get("ok") == True:
        print("tg 推送成功！")
    elif datas.get("error_code") == 400:
        print("tg 推送失败！请主动给 bot 发送一条消息并检查接收用户 TG_USER_ID 是否正确。")
    elif datas.get("error_code") == 401:
        print("tg 推送失败！TG_BOT_TOKEN 填写错误。")
    else:
        print(f"tg 推送失败！响应数据：{datas}")


def one() -> str:
    """
    获取一条一言。
    :return:
    """
    try:
        url = "https://v1.hitokoto.cn/"
        res = requests.get(url).json()
        return res["hitokoto"] + "    ----" + res["from"]
    except requests.exceptions.ConnectionError:
        return ""


if push_config.get("BARK_PUSH"):
    notify_function.append(bark)
if push_config.get("CONSOLE"):
    notify_function.append(console)
if push_config.get("DD_BOT_TOKEN") and push_config.get("DD_BOT_SECRET"):
    notify_function.append(dingding_bot)
if push_config.get("FSKEY"):
    notify_function.append(feishu_bot)
if push_config.get("GOBOT_URL") and push_config.get("GOBOT_QQ"):
    notify_function.append(go_cqhttp)
if push_config.get("IGOT_PUSH_KEY"):
    notify_function.append(iGot)
if push_config.get("PUSH_KEY"):
    notify_function.append(serverJ)
if push_config.get("PUSH_PLUS_TOKEN"):
    notify_function.append(pushplus_bot)
if push_config.get("QMSG_KEY") and push_config.get("QMSG_TYPE"):
    notify_function.append(qmsg_bot)
if push_config.get("QYWX_AM"):
    notify_function.append(wecom_app)
if push_config.get("QYWX_KEY"):
    notify_function.append(wecom_bot)
if push_config.get("TG_BOT_TOKEN") and push_config.get("TG_USER_ID"):
    notify_function.append(telegram_bot)
if push_config.get("MI_PUSH_ALIAS"):
    notify_function.append(mi_push)


def excepthook(args, /):
    if issubclass(args.exc_type, requests.exceptions.RequestException):
        print(
            f"网络异常，请检查你的网络连接、推送服务器和代理配置，该错误和账号配置无关。信息：{str(args.exc_type)}, {args.thread.name}"
        )
    elif issubclass(args.exc_type, json.JSONDecodeError):
        print(
            f"推送返回值非 json 格式，请检查网址和账号是否填写正确。信息：{str(args.exc_type)}, {args.thread.name}"
        )
    else:
        global default_hook
        default_hook(args)


default_hook = threading.excepthook
threading.excepthook = excepthook


def send(title: str, content: str) -> None:
    if not content:
        print(f"{title} 推送内容为空！")
        return

    hitokoto = push_config.get("HITOKOTO")

    text = one() if hitokoto else ""
    content += "\n\n" + text

    ts = [
        threading.Thread(target=mode, args=(title, content), name=mode.__name__)
        for mode in notify_function
    ]
    [t.start() for t in ts]
    [t.join() for t in ts]


def main():
    send("title", "content")


if __name__ == "__main__":
    main()
