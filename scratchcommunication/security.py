from __future__ import annotations
import random, os, sys, math, attrs, hashlib, json
from io import BytesIO
from itertools import batched
from Crypto.Cipher import AES
from typing import Literal, Any, assert_never
from cryptography.hazmat.primitives.asymmetric import x25519
from binascii import unhexlify, hexlify


SECURITY_RSA = "RSA"
SECURITY_EC = "EC"

alphabet = "abcdefghijklmnopqrstuvwxyz"
special_characters = " .,-:;_'#!\"§$%&/()=?{[]}\\0123456789<>ß*"
chars = alphabet + alphabet.upper() + special_characters
char_to_idx = {char: idx for idx, char in enumerate(chars)}

def is_prime(n : int, t = 10):
    if n <= 1:
        return False
    if n <= 3:
        return True
    if n % 2 == 0:
        return False
    m = (n - 1) // 2
    j = 1
    while not m % 2:
        j += 1
        m = m // 2
    d = m
    for _ in range(t):
        a = random.randrange(2, n - 2)
        x = pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        for _ in range(j - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True

def find_new_prime(byte_length = 100):
  while True:
    prime = int.from_bytes(os.urandom(byte_length), sys.byteorder)
    if is_prime(prime):
      return prime

def create_new_keys(byte_length = 130):
  def try_create_keys(p : int, q : int):
    n = p * q
    totient = (p - 1) * (q - 1) // math.gcd(p - 1, q - 1)
    d = 3
    e = pow(d, -1, totient)
    return d, e, n
  while True:
    try:
      p, q = find_new_prime(byte_length), find_new_prime(byte_length)
      return try_create_keys(p, q)
    except Exception:
      pass
    

def scalar_multiply(*, scalar: str, point: str) -> str:
    scalar_bytes = unhexlify(scalar)
    point_bytes = unhexlify(point)
    
    private_key = x25519.X25519PrivateKey.from_private_bytes(scalar_bytes)
    
    public_key = x25519.X25519PublicKey.from_public_bytes(point_bytes)
    
    shared_key = private_key.exchange(public_key)
    
    return hexlify(shared_key).decode()

class ConnectSecurity(tuple):
  pass

class RSAKeys(ConnectSecurity):
  def __new__(cls, keys : tuple[int, int, int] = None, *, public_exponent : int = None, private_exponent : int = None, public_modulus : int = None):
    if keys is not None:
      public_exponent, private_exponent, public_modulus = keys
    if (public_exponent and private_exponent and public_modulus) is None:
      raise ValueError("No data supplied.")
    if not (isinstance(public_exponent, int) and isinstance(private_exponent, int) and isinstance(public_modulus, int)):
      raise ValueError("Invalid data supplied.")
    return super().__new__(cls, (public_exponent, private_exponent, public_modulus))
    
  def __repr__(self):
    return "<RSAKeys object>"

  @property
  def keys(self) -> tuple:
    return tuple(self)

  def encrypt(self, data : int) -> int:
    return pow(data, self[0], self[2])

  def decrypt(self, data : int) -> int:
    return pow(data, self[1], self[2])

  @classmethod
  def create_new_keys(cls, byte_length : int = 130):
    return cls(create_new_keys(byte_length))
  
  @property
  def public_keys(self) -> dict:
    return {"[secure] public exponent": self[0], "[secure] public modulus": self[2], "[secure] key exchange scheme": "RSA"}
  
class ECSecurity(ConnectSecurity):
  def __new__(cls, data : tuple[str, str, str]):
    data = data if len(data) == 3 else (*data, scalar_multiply(point=data[0], scalar=data[1]))
    return super().__new__(cls, data)
    
  def __repr__(self):
    return "<ECSecurity object>"

  @property
  def keys(self) -> tuple:
    return tuple(self)
  
  def decrypt(self, data : str) -> str:
    return scalar_multiply(point=data, scalar=self[1])
  
  @property
  def public_data(self) -> dict:
    return {"[secure] public base": self[0], "[secure] public point": self[2], "[secure] key exchange scheme": "EC"}

@attrs.define(frozen=True)
class OldSymmetricEncryption:
  key : int
  
  def encrypt(self, data : str, salt : int = 0) -> str:
    seed = random.randrange(1000, 9999)
    encrypted = f"{seed}:{len(data)}:"
    modulus = 13
    for i in str(self.key) + str(salt):
      modulus += int(i)
      modulus **= 2
      modulus %= seed ** 2
    shift = pow(124231, 1 << 5, modulus)
    for idx, i in enumerate(data + str(modulus)):
      shift += idx
      shift **= 2
      shift %= modulus
      encrypted += chars[(char_to_idx[i] + shift) % len(chars)]
    return encrypted

  def decrypt(self, data : str, salt : int = 0) -> str:
    decrypted = ""
    seed, message_length, encrypted = data.split(":", 2)
    seed = int(seed)
    message_length = int(message_length)
    modulus = 13
    for i in str(self.key) + str(salt):
      modulus += int(i)
      modulus **= 2
      modulus %= seed ** 2
    shift = pow(124231, 1 << 5, modulus)
    for idx, i in enumerate(encrypted):
      shift += idx
      shift **= 2
      shift %= modulus
      decrypted += chars[(char_to_idx[i] - shift) % len(chars)]
    if not decrypted.endswith(str(modulus)) or message_length + len(str(modulus)) != len(decrypted):
      raise ValueError("Bad message")
    decrypted = decrypted.removesuffix(str(modulus))
    return decrypted
  
@attrs.define
class SymmetricEncryption:
  key : int
  hashed_key : bytes = attrs.field(init=False)
  
  def __init__(self, key : int, hashed_key : bytes = None) -> None:
    self.key = key
    self.hashed_key = hashed_key or hashlib.sha256(bytes(str(key), "utf-8")[-53:]).digest()[:16]
  
  def encrypt(self, data : str, salt : int) -> str:
    seed = random.randrange(1000, 9999)
    encrypted = f"{seed}:{len(data)}:"
    aes = AES.new(bin_xor(self.hashed_key, salt), AES.MODE_ECB)
    aes_pass = 0
    shifts = None
    data += "ITSTHEENDOFTHIS"
    for idx, i in enumerate(data):
      if not shifts:
        aes_pass += 1
        shifts = list(aes.encrypt(aes_pass.to_bytes(16)))
      shift = shifts.pop(0)
      encrypted += chars[(char_to_idx[i] + shift) % len(chars)]
    return encrypted

  def decrypt(self, data : str, salt : int = 0) -> str:
    decrypted = ""
    seed, message_length, encrypted = data.split(":", 2)
    seed = int(seed)
    message_length = int(message_length)
    aes = AES.new(bin_xor(self.hashed_key, salt), AES.MODE_ECB)
    aes_pass = 0
    shifts = None
    for idx, i in enumerate(encrypted):
      if not shifts:
        aes_pass += 1
        shifts = list(aes.encrypt(aes_pass.to_bytes(16)))
      shift = shifts.pop(0)
      decrypted += chars[(char_to_idx[i] - shift) % len(chars)]
    if not decrypted.endswith("ITSTHEENDOFTHIS") or message_length + len("ITSTHEENDOFTHIS") != len(decrypted):
      raise ValueError("Bad message")
    decrypted = decrypted.removesuffix("ITSTHEENDOFTHIS")
    return decrypted
  
def bin_xor(__bytes : bytes, number : int):
  byte_list = [int("".join(a)) for a in batched(str(number), 2)]
  return (f_p := bytes(a ^ b for a, b in zip(__bytes, byte_list)))+__bytes[len(f_p):]

@attrs.define
class Security:
  security_type : Literal["RSA", "EC"] = attrs.field(kw_only=True)
  data : Any = attrs.field(kw_only=True)
  
  @classmethod
  def generate(cls, __type : Literal["RSA", "EC"] = "EC") -> Security:
    if __type == "RSA":
      return cls(data=RSAKeys.create_new_keys().keys, security_type="RSA")
    if __type != "EC":
      assert_never()
    scalar = bytearray(os.urandom(32))
    
    scalar[0] &= 248
    scalar[31] &= 127
    scalar[31] |= 64
    
    data = bytes(scalar).hex()
    
    return cls(data=("0900000000000000000000000000000000000000000000000000000000000000", data), security_type="EC")
  
  @property
  def public_data(self) -> dict:
    if self.security_type == "RSA":
      return RSAKeys(self.data).public_keys
    if self.security_type == "EC":
      return ECSecurity(self.data).public_data
    
  def to_string(self) -> str:
    data = BytesIO()
    if self.security_type == "RSA":
      data.write(b"RSAxxxx1")
    elif self.security_type == "EC":
      data.write(b"ECxxxxx1")
    else:
      raise ValueError("Unknown format")
    data.write(json.dumps(self.data).encode("utf-8"))
    return data.getvalue().decode("utf-8")
    
  @classmethod
  def from_string(cls, data : str) -> Security:
    s_type = data[:8]
    if s_type == "RSAxxxx1":
      s_type = "RSA"
    elif s_type == "ECxxxxx1":
      s_type = "EC"
    else:
      raise ValueError("Unknown format")
    data = data[8:]
    data = json.loads(data)
    return cls(security_type=s_type, data=data)