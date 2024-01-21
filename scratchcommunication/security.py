import random, os, sys, math, attrs

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

class RSAKeys(tuple):
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
    return {"public_exponent": self[0], "public_modulus": self[2]}

@attrs.define(frozen=True)
class SymmetricEncryption:
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