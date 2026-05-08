import os
import base64

#read if originally got key or not 
def get_groq_key() -> str:

    return ""


    # k = os.getenv("GROQ_API_KEY", "").strip()
    # if k:
    #     return k

    # #encode the key by making it into base64 (scrambled)
    # b64 = "WU9VUl9HUk9RX0FQSV9LRVlfSEVSRQ=="
    # return base64.b64decode(b64).decode("utf-8").strip()
