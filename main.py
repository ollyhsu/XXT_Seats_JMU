import random
import requests
import requests.utils
from lxml import etree
import re
from Crypto.Cipher import AES
from Crypto.Hash import MD5
import base64
from datetime import datetime
from fake_useragent import UserAgent
import time
import json

seatId = "90"  # JMU（需要抓包获取）
roomId = "125"  # 延奎馆四楼 A区寄包柜 124; 嘉庚馆二楼 B区寄包柜 125; 嘉庚馆二楼 C区寄包柜 126
seatNum_list = ["13", "15", "270"]  # 设置心仪的座位ID
info = [["姓名（可写可不写）", "11111", "123456"]]  # 登录信息


# URL 信息
url_index = "https://office.chaoxing.com/front/apps/seatengine/index?seatId={}"
url_select = "http://office.chaoxing.com/front/third/apps/seatengine/select?id={}&day={}&backLevel=2&seatId={}"

url_submit = "http://office.chaoxing.com/data/apps/seatengine/submit?roomId={}&startTime={}&endTime={}&day={}&captcha=&seatNum={}&token={}&enc={}"
url_cancel = "http://office.chaoxing.com/data/apps/seatengine/cancel?id={}"

url_index_data = "http://office.chaoxing.com/data/apps/seatengine/index?seatId={}"
url_yuyue_data = "https://office.chaoxing.com/data/apps/seatengine/reservelist?cpage=1&pageSize=10&type=-1&seatId={}"

url_used_data = "http://office.chaoxing.com/data/apps/seatengine/getusedseatnums?seatId={}&roomId={}&startTime={}&endTime={}&day={}"
url_room_data = "http://office.chaoxing.com/data/apps/seatengine/room/info?id={}&toDay={}"


# 登录的加密函数
def encrpytByAES(message, key):
    key = "u2oh6Vu^HWe4_AES"
    iv = key.encode("utf-8")
    message = message.encode("utf-8")

    # 使用PKCS7Padding填充
    BS = AES.block_size

    def padding(s):
        return s + (BS - len(s) % BS) * chr(BS - len(s) % BS).encode()

    cipher = AES.new(iv, AES.MODE_CBC, iv)
    ciphertext = cipher.encrypt(padding(message))
    return base64.b64encode(ciphertext).decode("utf-8")


# 使用session保存cookies
def getCookies(data, headers):
    url = "https://passport2.chaoxing.com/fanyalogin"
    # proxy = {"http": "http://127.0.0.1:8080"}
    resp = requests.session()
    resp.headers = headers
    resp.post(url, data=data)
    url1 = url_index.format(seatId)
    resp.get(url=url1)
    return resp


def getToken(session, today):
    # proxy = {"http": "http://127.0.0.1:8080"}
    url = url_select.format(roomId, today, seatId)
    resp = session.get(url)
    res = etree.HTML(resp.text)
    script = res.xpath("/html/body/script[3]/text()")[0]
    pattern = re.compile("token = '(?P<token>.*?)'")
    token = pattern.search(script)
    if token:
        token = token.group("token")
        return token
    else:
        return None


def getSeat(sess, roomId, startTime, endTime, day, seatNum, token, enc):
    # proxy = {"http": "http://127.0.0.1:8080"}
    seatNum1 = str(seatNum).rjust(3, "0")
    url = url_submit.format(roomId, startTime, endTime,
                            day, seatNum1, token, enc)
    resp = sess.get(url)
    status = json.loads(resp.text)["success"]

    if status == True:
        firstLevelName = json.loads(
            resp.text)["data"]["seatReserve"]["firstLevelName"]
        secondLevelName = json.loads(resp.text)["data"]["seatReserve"][
            "secondLevelName"
        ]
        thirdLevelName = json.loads(
            resp.text)["data"]["seatReserve"]["thirdLevelName"]
        seatNum_id = json.loads(resp.text)["data"]["seatReserve"]["seatNum"]
        seat_info = (
            firstLevelName + secondLevelName + " " + thirdLevelName + " " + seatNum_id
        )
    else:
        seat_info = json.loads(resp.text)["msg"]
    return status, seat_info


def getData(info):
    data = {
        "fid": "-1",
        "uname": encrpytByAES(info[1], 0),
        "password": encrpytByAES(info[2], 0),
        "refer": url_index.format(seatId),
        "t": "true",
        "forbidotherlogin": "0",
        "validate": "",
        "doubleFactorLogin": "0",
        "independentId": "0",
    }
    return data


def getEnc(today, endTime, seatNum, startTime, token, roomId):
    content = "[captcha=][day={}][endTime={}][roomId={}][seatNum={}][startTime={}][token={}][%sd`~7^/>N4!Q#){kuohao}'']".format(
        today, endTime, roomId, seatNum, startTime, token, kuohao="{"
    )
    result = MD5.new()
    result.update(content.encode("utf-8"))
    return result.hexdigest()


# 查询已有预约
def get_yuyue(sess):
    resp = sess.get(url_yuyue_data.format(seatId))
    # Parse the JSON data
    parsed_data = json.loads(resp.text)
    # Extract starttime and endtime
    statusId = parsed_data["data"]["reserveList"][0]["status"]
    if statusId == 0:
        yuyueId = parsed_data["data"]["reserveList"][0]["id"]
        # print(yuyueId)
        return yuyueId
    else:
        print("您当前没有预约记录！")
        return 0


# 取消预约
def get_cancel(sess):
    yuyue_id = get_yuyue(sess)
    r = sess.get(url_cancel.format(yuyue_id))
    if r.json()["success"] == True:
        print("取消预约成功！\n")
        return True
    else:
        print("取消预约失败！" + r.json()["msg"] + "\n")
        return False


# 获取开始和结束时间
def getSETime(sess):
    resp = sess.get(url_index_data.format(seatId))
    # Parse the JSON data
    parsed_data = json.loads(resp.text)
    # Extract starttime and endtime
    startDate = parsed_data["data"]["seatConfig"]["startDate"]
    endDate = parsed_data["data"]["seatConfig"]["endDate"]
    # print(startDate, endDate)
    return startDate, endDate


# 查询已用座位
# 返回的是数组，已使用的座位号在里面
def get_used(sess, roomId, startTime, endTime, day):
    r = sess.get(url_used_data.format(seatId, roomId, startTime, endTime, day))
    data = r.json()["data"]["seatReserves"]
    # 取出所有 seatNum
    seat_nums = [entry["seatNum"] for entry in data]
    # 从小到大排序
    sorted_seat_used_nums = sorted(seat_nums)
    # print(sorted_seat_used_nums)
    return sorted_seat_used_nums


# 查询全部容量
# https://reserve.chaoxing.com/data/apps/apps/seatengine/list?deptIdEnc=&seatId=90
def get_room_capacity(sess, roomId, day):
    r = sess.get(url_room_data.format(roomId, day))
    capacity = r.json()["data"]["seatRoom"]["capacity"]
    return capacity


# 随机查找剩余空位
def get_random_unused_seat(sess, roomId, day, startTime, endTime):
    capacity = get_room_capacity(sess, roomId, day)
    used_list = get_used(sess, roomId, startTime, endTime, day)

    all_list = [f"{i:03}" for i in range(1, capacity + 1)]
    unused_list = [x for x in all_list if x not in used_list]
    # print(unused_list)
    unusedId = random.choice(unused_list)
    return unusedId


def xxt_seat():
    ua = UserAgent()
    ua = ua.random
    headers = {"user-agent": ua}

    # 获取data
    mdata = getData(info[0])

    # 获取session
    msession = getCookies(mdata, headers)

    today = datetime.now().strftime("%Y-%m-%d")

    # 获取必要的token
    mtoken = getToken(msession, today)

    startDate, endDate = getSETime(msession)
    # print( startDate, endDate )

    # get_cancel(msession)

    # enc获取
    found_seat = False  # 添加标志表示是否找到可用座位

    for num in seatNum_list:
        if found_seat:  # 如果已经找到座位则退出循环
            break

        ct = [[msession, num, startDate, endDate, mtoken, roomId]]

        # 添加enc
        for item in ct:
            seatNum = str(item[1]).rjust(3, "0")  # 传入的座位号为0xx
            startTime = item[2]
            endTime = item[3]
            token = item[4]
            room_id = item[5]
            item.append(getEnc(today, endTime, seatNum,
                        startTime, token, room_id))

        max_attempts = 2  # 最大尝试次数
        attempts = 0

        while attempts < max_attempts:
            print(f"尝试座位: {num}")
            t = datetime.now().strftime("%H:%M:%S")
            if t:
                print(datetime.now())
                for session, seatNum, startTime, endTime, token, room_id, enc in ct:
                    status, seat_info = getSeat(
                        session, roomId, startTime, endTime, today, seatNum, token, enc
                    )
                    if status is True:
                        print(seat_info + " 预约成功~")
                        found_seat = True  # 设置找到座位标志
                        break
                    elif status is False:
                        if seat_info == "该时间段您已有预约！":
                            print(seat_info)
                            found_seat = True  # 设置找到座位标志
                            exit(0)  # 有预约则退出
                            # break
                        else:
                            print(seat_info)
                            attempts += 1
                            if attempts == max_attempts:
                                print(f"尝试了最大次数\n")
                                random_seatid = get_random_unused_seat(
                                    msession, roomId, today, startDate, endDate)
                                break
                    else:
                        print("错误~")
                        break
                if found_seat:  # 如果找到座位，直接退出外部循环
                    break
            else:
                time.sleep(0.1)

    # 如果循环结束未找到座位，将unusedid赋值为num，调用getSeat
    if not found_seat:
        num = random_seatid
        print("随机ID: " + num)

        ct = [[msession, num, startDate, endDate, mtoken, roomId]]

        # 添加enc
        for item in ct:
            seatNum = str(item[1]).rjust(3, "0")  # 传入的座位号为0xx
            startTime = item[2]
            endTime = item[3]
            token = item[4]
            room_id = item[5]
            item.append(getEnc(today, endTime, seatNum,
                        startTime, token, room_id))

        max_attempts = 2  # 最大尝试次数
        attempts = 0

        while attempts < max_attempts:
            print(f"尝试座位: {num}")
            t = datetime.now().strftime("%H:%M:%S")
            if t:
                print(datetime.now())
                for session, seatNum, startTime, endTime, token, room_id, enc in ct:
                    status, seat_info = getSeat(
                        session, roomId, startTime, endTime, today, seatNum, token, enc
                    )
                    if status is True:
                        print(seat_info + " 预约成功~")
                        found_seat = True  # 设置找到座位标志
                        break
                    elif status is False:
                        print(seat_info)
                        attempts += 1
                        if attempts == max_attempts:
                            print(f"尝试了最大次数\n")
                            break
                    else:
                        print("错误~")
                        break
                if found_seat:  # 如果找到座位，直接退出外部循环
                    break
            else:
                time.sleep(0.1)
    else:
        print("~~~\n")


def get_current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main():
    target_time = datetime(2024, 3, 5, 12, 7)  # 设置定时时间
    target_end_time = datetime(2024, 3, 7, 9, 42)

    while True:
        current_time = datetime.now()

        print("Current Time:", get_current_time())

        if current_time >= target_time:
            print("Time reached!")
            xxt_seat()

        if current_time >= target_end_time:
            print("定时器关闭~")
            break

        time.sleep(0.5)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e)
