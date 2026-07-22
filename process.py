import base64
import json
import os
import re
import socket
import sys
import urllib.parse
import urllib.request
import qrcode
import requests
import yaml

# ساخت پوشه‌ها
for folder in ["sub-raw", "sub-clash", "sub-json"]:
  os.makedirs(folder, exist_ok=True)


def get_flag_emoji(country_code):
  """تبدیل کد دو حرفی کشور به ایموجی پرچم"""
  if not country_code or len(country_code) != 2:
    return "🌐"
  country_code = country_code.upper()
  return chr(ord(country_code[0]) + 127397) + chr(
      ord(country_code[1]) + 127397
  )


def get_server_location(host):
  """استخراج کشور و پرچم از روی IP یا آدرس دامنه"""
  try:
    ip = socket.gethostbyname(host)
    response = requests.get(
        f"http://ip-api.com/json/{ip}?fields=countryCode", timeout=3
    )
    if response.status_code == 200:
      code = response.json().get("countryCode", "")
      return get_flag_emoji(code)
  except Exception:
    pass
  return "🌐"


def generate_qr(link, qr_filepath):
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
  except Exception as e:
    print(f"⚠️ ارور ساخت QR: {e}")


def fetch_content(url):
  req = urllib.request.Request(
      url,
      headers={
          "User-Agent": (
              "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          )
      },
  )
  try:
    with urllib.request.urlopen(req, timeout=12) as response:
      return response.read().decode("utf-8")
  except Exception as e:
    print(f"⚠️ خطا در دریافت {url}: {e}")
    return ""


def get_next_filename(folder_path, prefix="sub", extension=".txt"):
  count = 1
  while True:
    filename = f"{prefix}_{count}{extension}"
    if not os.path.exists(os.path.join(folder_path, filename)):
      return filename
    count += 1


def extract_host_from_uri(uri):
  try:
    if "://" in uri:
      clean_uri = uri.split("://")[1].split("#")[0]
      if "@" in clean_uri:
        host_port = clean_uri.split("@")[1].split("?")[0]
      else:
        host_port = clean_uri.split("?")[0]
      return host_port.split(":")[0]
  except Exception:
    pass
  return None


# ==========================================
# ۱. پردازش RAW (ترکیب + پرچم + اسم‌گذاری)
# ==========================================
def process_raw(urls, custom_name, repo_info):
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

  new_lines = []
  index = 1

  print("🌐 در حال استخراج پرچم کشورها برای سرورها...")
  for line in all_lines:
    if line.startswith(
        ("vless://", "vmess://", "trojan://", "ss://", "socks://")
    ):
      base_part = line.rsplit("#", 1)[0] if "#" in line else line
      host = extract_host_from_uri(line)
      flag = get_server_location(host) if host else "🌐"

      new_title_str = f"{flag} {custom_name} {index:02d}"
      new_title_encoded = urllib.parse.quote(new_title_str)

      new_lines.append(f"{base_part}#{new_title_encoded}")
      index += 1

  if not new_lines:
    print("❌ هیچ کانفیگ معتبری یافت نشد!")
    return

  result_text = "\n".join(new_lines)
  encoded_result = base64.b64encode(result_text.encode("utf-8")).decode("utf-8")

  filename = get_next_filename("sub-raw", "sub", ".txt")
  filepath = os.path.join("sub-raw", filename)

  with open(filepath, "w", encoding="utf-8") as f:
    f.write(encoded_result)

  print(f"✅ ساب RAW جدید ساخته شد ({len(new_lines)} سرور): {filepath}")

  if repo_info:
    raw_url = f"https://raw.githubusercontent.com/{repo_info}/main/sub-raw/{filename}"
    qr_path = os.path.join("sub-raw", f"{os.path.splitext(filename)[0]}_qr.png")
    generate_qr(raw_url, qr_path)


# ==========================================
# ۲. پردازش CLASH (ترکیب + پرچم + اسم‌گذاری)
# ==========================================
def process_clash(urls, custom_name, repo_info):
  all_proxies = []
  for url in urls:
    content = fetch_content(url)
    if not content:
      continue
    try:
      data = yaml.safe_load(content)
      if data and isinstance(data, dict) and "proxies" in data:
        all_proxies.extend(data["proxies"])
    except Exception as e:
      print(f"⚠️ ارور خواندن کلش: {e}")

  if not all_proxies:
    print("❌ هیچ پروکسی کلش پیدا نشد!")
    return

  index = 1
  for proxy in all_proxies:
    if isinstance(proxy, dict) and "name" in proxy:
      server_host = proxy.get("server", "")
      flag = get_server_location(server_host) if server_host else "🌐"
      proxy["name"] = f"{flag} {custom_name} {index:02d}"
      index += 1

  clash_config = {
      "port": 7890,
      "socks-port": 7891,
      "allow-lan": True,
      "mode": "rule",
      "proxies": all_proxies,
      "proxy-groups": [
          {
              "name": custom_name,
              "type": "select",
              "proxies": [p["name"] for p in all_proxies if "name" in p],
          }
      ],
  }

  filename = get_next_filename("sub-clash", "clash", ".yaml")
  filepath = os.path.join("sub-clash", filename)

  with open(filepath, "w", encoding="utf-8") as f:
    yaml.dump(
        clash_config, f, allow_unicode=True, sort_keys=False, default_flow_style=False
    )

  print(f"✅ ساب Clash با موفقیت ساخته شد: {filepath}")

  if repo_info:
    raw_url = f"https://raw.githubusercontent.com/{repo_info}/main/sub-clash/{filename}"
    qr_path = os.path.join(
        "sub-clash", f"{os.path.splitext(filename)[0]}_qr.png"
    )
    generate_qr(raw_url, qr_path)


# ==========================================
# ۳. پردازش JSON / Sing-box (ترکیب + پرچم + اسم‌گذاری)
# ==========================================
def process_json(urls, custom_name, repo_info):
  all_outbounds = []
  for url in urls:
    content = fetch_content(url)
    if not content:
      continue
    try:
      data = json.loads(content)
      outbounds = data.get("outbounds", []) if isinstance(data, dict) else data
      if isinstance(outbounds, list):
        all_outbounds.extend(outbounds)
    except Exception as e:
      print(f"⚠️ ارور خواندن JSON: {e}")

  if not all_outbounds:
    print("❌ هیچ داده JSON معتبری پیدا نشد!")
    return

  index = 1
  for item in all_outbounds:
    if isinstance(item, dict) and "tag" in item:
      server_host = item.get("server", "")
      flag = get_server_location(server_host) if server_host else "🌐"
      item["tag"] = f"{flag} {custom_name} {index:02d}"
      index += 1

  final_json = {"remarks": custom_name, "outbounds": all_outbounds}

  filename = get_next_filename("sub-json", "json", ".json")
  filepath = os.path.join("sub-json", filename)

  with open(filepath, "w", encoding="utf-8") as f:
    json.dump(final_json, f, ensure_ascii=False, indent=2)

  print(f"✅ ساب JSON جدید ساخته شد: {filepath}")

  if repo_info:
    raw_url = f"https://raw.githubusercontent.com/{repo_info}/main/sub-json/{filename}"
    qr_path = os.path.join(
        "sub-json", f"{os.path.splitext(filename)[0]}_qr.png"
    )
    generate_qr(raw_url, qr_path)


# ==========================================
# مدیریت اصلی
# ==========================================
if __name__ == "__main__":
  if len(sys.argv) > 3:
    sub_type = sys.argv[1].strip()
    urls_text = sys.argv[2].strip()
    base_name = sys.argv[3].strip()
    repo_info = sys.argv[4].strip() if len(sys.argv) > 4 else None

    urls = [u.strip() for u in re.split(r"[\n\r\s]+", urls_text) if u.strip()]

    if "Raw" in sub_type or sub_type == "1":
      process_raw(urls, base_name, repo_info)
    elif "Clash" in sub_type or sub_type == "2":
      process_clash(urls, base_name, repo_info)
    elif "JSON" in sub_type or sub_type == "3":
      process_json(urls, base_name, repo_info)
  else:
    print("❌ ورودی‌ها کامل نیست.")