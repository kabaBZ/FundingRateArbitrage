from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import base64
import gzip
import io


def decryptAES(en_text, key):
    key = key.encode() if isinstance(key, str) else key
    en_text = en_text.encode() if isinstance(en_text, str) else en_text
    # AES.MODE_ECB 表示模式是ECB模式
    # 创建一个aes对象
    aes = AES.new(
        key,
        AES.MODE_ECB,
    )
    den_text = unpad(aes.decrypt(en_text), AES.block_size)  # 解密密文
    return den_text.hex()

def Yt(data, key):
    t = decryptAES(base64.b64decode(data), key)
    with gzip.GzipFile(fileobj=io.BytesIO(bytes.fromhex(t))) as f:
        # 解压缩数据
        decompressed_data = f.read()
    return decompressed_data.decode()

def decrypt_response(response):
    data = response.json()["data"]
    user = response.headers.get("user")
    # url_key
    n = base64.b64encode(
        "coinglass/api/fundingRate/interestArbitragecoinglass".encode()
    ).decode()
    n = n[:16]
    n = Yt(user, n)
    i = Yt(data, n)
    return i
