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

externalc2 = ExternalC2( "https://127.0.0.1:40056/ExtEndpoint" )
print("[+] connected to ExternalC2 endpoint")

while True:
    '''Loop process:
    - Poll data from website
    - Decode data
    - Transmit data to ExternalC2 endpoint
            response = externalc2.transmit()
            print("RESPONSE: " + response.decode('utf-8') + "\n")
    - Sleep for 5 seconds
            time.sleep(5)
    '''
    
    