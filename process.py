import base64
import json
import os
import sys
import urllib.parse
import urllib.request
import yaml

# ساخت پوشه‌ها در صورت عدم وجود
for folder in ["sub-raw", "sub-clash", "sub-json"]:
  os.makedirs(folder, exist_ok=True)


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
  with urllib.request.urlopen(req) as response:
    return response.read().decode("utf-8")


def get_next_filename(folder_path, prefix="sub", extension=".txt"):
  """نام‌گذاری خودکار فایل جدید بدون خراب کردن فایل‌های قبلی"""
  count = 1
  while True:
    filename = f"{prefix}_{count}{extension}"
    if not os.path.exists(os.path.join(folder_path, filename)):
      return filename
    count += 1


# ==========================================
# ۱. پردازش RAW (V2ray Base64 / URIs)
# ==========================================
def process_raw(url, custom_name):
  content = fetch_content(url).strip()

  try:
    decoded = base64.b64decode(content).decode("utf-8")
    lines = [line.strip() for line in decoded.splitlines() if line.strip()]
  except Exception:
    lines = [line.strip() for line in content.splitlines() if line.strip()]

  new_lines = []
  index = 1

  for line in lines:
    if "#" in line:
      base_part = line.rsplit("#", 1)[0]
      new_title = urllib.parse.quote(f"{custom_name} {index:02d}")
      new_lines.append(f"{base_part}#{new_title}")
      index += 1
    else:
      new_lines.append(line)

  result_text = "\n".join(new_lines)
  encoded_result = base64.b64encode(result_text.encode("utf-8")).decode("utf-8")

  filename = get_next_filename("sub-raw", "sub", ".txt")
  filepath = os.path.join("sub-raw", filename)

  with open(filepath, "w", encoding="utf-8") as f:
    f.write(encoded_result)

  print(f"✅ ساب RAW جدید ساخته شد: {filepath}")


# ==========================================
# ۲. پردازش CLASH (YAML بدون دستکاری ساختار)
# ==========================================
def process_clash(url, custom_name):
  content = fetch_content(url)
  data = yaml.safe_load(content)

  if not data or not isinstance(data, dict) or "proxies" not in data:
    print("❌ فایل کلش نامعتبر است یا پروکسی ندارد!")
    return

  name_map = {}
  index = 1

  for proxy in data["proxies"]:
    if isinstance(proxy, dict) and "name" in proxy:
      old_name = proxy["name"]
      new_name = f"{custom_name} {index:02d}"
      proxy["name"] = new_name
      name_map[old_name] = new_name
      index += 1

  if "proxy-groups" in data and isinstance(data["proxy-groups"], list):
    for group in data["proxy-groups"]:
      if isinstance(group, dict) and "proxies" in group:
        group["proxies"] = [name_map.get(p, p) for p in group["proxies"]]

  filename = get_next_filename("sub-clash", "clash", ".yaml")
  filepath = os.path.join("sub-clash", filename)

  with open(filepath, "w", encoding="utf-8") as f:
    yaml.dump(
        data,
        f,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )

  print(f"✅ ساب Clash جدید ساخته شد: {filepath}")


# ==========================================
# ۳. پردازش JSON (Sing-box / Xray JSON)
# ==========================================
def process_json(url, custom_name):
  content = fetch_content(url)
  data = json.loads(content)

  index = 1
  name_map = {}

  outbounds = data.get("outbounds", []) if isinstance(data, dict) else data

  if isinstance(outbounds, list):
    for item in outbounds:
      if isinstance(item, dict) and "tag" in item:
        old_tag = item["tag"]
        new_tag = f"{custom_name} {index:02d}"
        item["tag"] = new_tag
        name_map[old_tag] = new_tag
        index += 1

    for item in outbounds:
      if isinstance(item, dict) and "outbounds" in item:
        if isinstance(item["outbounds"], list):
          item["outbounds"] = [name_map.get(o, o) for o in item["outbounds"]]

  filename = get_next_filename("sub-json", "json", ".json")
  filepath = os.path.join("sub-json", filename)

  with open(filepath, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

  print(f"✅ ساب JSON جدید ساخته شد: {filepath}")


# ==========================================
# دریافت پارامترها از اکشن گیت‌هاب
# ==========================================
if __name__ == "__main__":
  if len(sys.argv) > 3:
    sub_type = sys.argv[1].strip()
    sub_url = sys.argv[2].strip()
    base_name = sys.argv[3].strip()

    if "Raw" in sub_type or sub_type == "1":
      process_raw(sub_url, base_name)
    elif "Clash" in sub_type or sub_type == "2":
      process_clash(sub_url, base_name)
    elif "JSON" in sub_type or sub_type == "3":
      process_json(sub_url, base_name)
    else:
      print("❌ نوع ساب نامعتبر است!")
  else:
    print("❌ ورودی‌های کافی ارسال نشده است.")
