import base64
import json
import os
import re
import socket
import sys
import urllib.parse
import urllib.request
import qrcode
import yaml

# ساخت پوشه‌ها
for folder in ["sub-raw", "sub-clash", "sub-json"]:
  os.makedirs(folder, exist_ok=True)


def generate_qr(link, qr_filepath):
  """تولید عکس QR Code برای لینک ساب"""
  try:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(qr_filepath)
    print(f"🖼️ عکس QR Code ذخیره شد: {qr_filepath}")
  except Exception as e:
    print(f"⚠️ ارور در ساخت QR Code: {e}")


def fetch_content(url):
  """دریافت محتوای ساب با هدر کاربر واقعی"""
  req = urllib.request.Request(
      url,
      headers={
          "User-Agent": (
              "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
              " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
          )
      },
  )
  try:
    with urllib.request.urlopen(req, timeout=10) as response:
      return response.read().decode("utf-8")
  except Exception as e:
    print(f"⚠️ خطا در دریافت لینک {url}: {e}")
    return ""


def get_next_filename(folder_path, prefix="sub", extension=".txt"):
  """نام‌گذاری خودکار فایل جدید"""
  count = 1
  while True:
    filename = f"{prefix}_{count}{extension}"
    if not os.path.exists(os.path.join(folder_path, filename)):
      return filename
    count += 1


def is_host_alive(host, port, timeout=2):
  """تست پایه اتصال به آدرس و پورت سرور"""
  try:
    port = int(port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    result = sock.connect_ex((host, port))
    sock.close()
    return result == 0
  except Exception:
    return False


# ==========================================
# استخراج کانفیگ‌های RAW
# ==========================================
def extract_raw_configs(urls):
  all_lines = []
  for url in urls:
    content = fetch_content(url).strip()
    if not content:
      continue

    try:
      decoded = base64.b64decode(content).decode("utf-8")
      lines = [line.strip() for line in decoded.splitlines() if line.strip()]
    except Exception:
      lines = [line.strip() for line in content.splitlines() if line.strip()]

    all_lines.extend(lines)

  return all_lines


def rename_and_filter_raw(lines, custom_name):
  processed = []
  index = 1
  for line in lines:
    if "#" in line:
      base_part = line.rsplit("#", 1)[0]
      new_title = urllib.parse.quote(f"{custom_name} {index:02d}")
      processed.append(f"{base_part}#{new_title}")
      index += 1
    elif line.startswith(("vless://", "vmess://", "trojan://", "ss://")):
      new_title = urllib.parse.quote(f"{custom_name} {index:02d}")
      processed.append(f"{line}#{new_title}")
      index += 1
  return processed


# ==========================================
# پردازش اصلی (ادغام و ساخت تمام فرمت‌ها)
# ==========================================
def process_subscriptions(urls_text, custom_name, repo_info):
  # جداسازی لینک‌های ورودی که با خط بعد یا فاصله جدا شده‌اند
  urls = [u.strip() for u in re.split(r"[\n\r\s]+", urls_text) if u.strip()]

  if not urls:
    print("❌ هیچ لینکی دریافت نشد!")
    return

  print(f"🔄 در حال پردازش {len(urls)} لینک ورودی...")

  # ۱. دریافت و ترکیب لینک‌های RAW
  raw_lines = extract_raw_configs(urls)
  final_raw_lines = rename_and_filter_raw(raw_lines, custom_name)

  if not final_raw_lines:
    print("❌ هیچ کانفیگ معتبری یافت نشد!")
    return

  # ۲. ذخیره فایل RAW
  raw_filename = get_next_filename("sub-raw", "sub", ".txt")
  raw_filepath = os.path.join("sub-raw", raw_filename)
  result_text = "\n".join(final_raw_lines)
  encoded_result = base64.b64encode(result_text.encode("utf-8")).decode("utf-8")

  with open(raw_filepath, "w", encoding="utf-8") as f:
    f.write(encoded_result)
  print(f"✅ ساب RAW ساخته شد ({len(final_raw_lines)} سرور): {raw_filepath}")

  if repo_info:
    raw_url = f"https://raw.githubusercontent.com/{repo_info}/main/sub-raw/{raw_filename}"
    qr_path = os.path.join(
        "sub-raw", f"{os.path.splitext(raw_filename)[0]}_qr.png"
    )
    generate_qr(raw_url, qr_path)


# ==========================================
# دریافت پارامترها از اکشن گیت‌هاب
# ==========================================
if __name__ == "__main__":
  if len(sys.argv) > 3:
    _ = sys.argv[1].strip()  # sub_type
    sub_urls = sys.argv[2].strip()
    base_name = sys.argv[3].strip()
    repo_info = sys.argv[4].strip() if len(sys.argv) > 4 else None

    process_subscriptions(sub_urls, base_name, repo_info)
  else:
    print("❌ ورودی‌های کافی ارسال نشده است.")
