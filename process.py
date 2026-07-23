import base64
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import qrcode
import yaml

# ساخت پوشه‌های مورد نیاز
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

def safe_b64decode(s):
    """دکود ایمن بیس۶۴ با پدینگ خودکار"""
    if not s:
        return ""
    s = s.strip().replace("\r", "").replace("\n", "")
    missing_padding = len(s) % 4
    if missing_padding:
        s += '=' * (4 - missing_padding)
    try:
        return base64.b64decode(s).decode('utf-8', errors='ignore')
    except Exception:
        return s

def fetch_or_read(input_item):
    """دریافت محتوا (اگر URL بود دانلود می‌کند، اگر کانفیگ مستقیم بود همان را برمی‌گرداند)"""
    input_item = input_item.strip()
    if input_item.startswith(('http://', 'https://')):
        req = urllib.request.Request(
            input_item,
            headers={"User-Agent": "v2rayNG/1.8.12 (com.v2ray.ang; build 500; Android 13)"}
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                return response.read().decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"⚠️ خطا در دریافت لینک {input_item}: {e}")
            return ""
    else:
        # ورودی متن مستقیم کانفیگ است
        return input_item

def extract_configs_from_text(text):
    """استخراج تمامی لینک‌های پروکسی از متن خامی یا بیس۶۴"""
    if not text:
        return []
    
    # تست دکود بیس۶۴ کل متن
    decoded = safe_b64decode(text)
    working_text = decoded if any(p in decoded for p in ["vless://", "vmess://", "trojan://", "ss://"]) else text

    # استخراج تمام پروکسی‌ها با الگوی جامع
    pattern = r'(?:vless|vmess|trojan|ss|socks|hy2|tuic)://[^\s"#]+(?:#[^\s"]*)?'
    found = re.findall(pattern, working_text)
    
    if not found:
        # اگر با الگوی فوق پیدا نشد، خط به خط بررسی کن
        lines = [line.strip() for line in working_text.splitlines() if line.strip()]
        for line in lines:
            if any(line.startswith(p) for p in ["vless://", "vmess://", "trojan://", "ss://", "socks://", "hy2://", "tuic://"]):
                found.append(line)
                
    return found

def get_next_filename(folder_path, prefix="sub", extension=".txt"):
    """نام‌گذاری خودکار فایل جدید"""
    count = 1
    while True:
        filename = f"{prefix}_{count}{extension}"
        if not os.path.exists(os.path.join(folder_path, filename)):
            return filename
        count += 1

# ==========================================
# پارسر جامع پروکسی‌ها جهت تبدیل به کلش
# ==========================================
def parse_uri_to_clash(link):
    """استخراج تمام جزییات شبکه جهت ساخت ساختار کلش"""
    try:
        link = link.strip()
        if not link:
            return None

        # ۱. VLESS
        if link.startswith('vless://'):
            parsed = urllib.parse.urlparse(link)
            user_info = parsed.netloc.split('@')
            uuid = user_info[0]
            host_port = user_info[1].split(':')
            server = host_port[0]
            port = int(host_port[1])
            params = urllib.parse.parse_qs(parsed.query)
            remark = urllib.parse.unquote(parsed.fragment) or "VLESS"

            security = params.get('security', [''])[0]
            net_type = params.get('type', [''])[0]

            proxy = {
                'name': remark,
                'type': 'vless',
                'server': server,
                'port': port,
                'uuid': uuid,
                'udp': True,
                'tls': security in ['tls', 'reality'],
                'skip-cert-verify': True
            }

            if security == 'reality':
                proxy['reality-opts'] = {'public-key': params.get('pbk', [''])[0]}
                if 'sid' in params:
                    proxy['reality-opts']['short-id'] = params['sid'][0]

            if 'sni' in params:
                proxy['servername'] = params['sni'][0]
            if 'fp' in params:
                proxy['client-fingerprint'] = params['fp'][0]
            if 'alpn' in params:
                proxy['alpn'] = params['alpn'][0].split(',')

            if net_type == 'ws':
                proxy['network'] = 'ws'
                proxy['ws-opts'] = {'path': params.get('path', ['/'])[0]}
                if 'host' in params:
                    proxy['ws-opts']['headers'] = {'Host': params['host'][0]}
            elif net_type == 'grpc':
                proxy['network'] = 'grpc'
                proxy['grpc-opts'] = {'grpc-service-name': params.get('serviceName', params.get('path', ['']))[0]}

            return proxy

        # ۲. VMESS
        elif link.startswith('vmess://'):
            b64_part = link.replace('vmess://', '')
            decoded_json = safe_b64decode(b64_part)
            data = json.loads(decoded_json)

            proxy = {
                'name': data.get('ps', 'VMess'),
                'type': 'vmess',
                'server': data.get('add'),
                'port': int(data.get('port', 443)),
                'uuid': data.get('id'),
                'alterId': int(data.get('aid', 0)),
                'cipher': 'auto',
                'udp': True,
                'tls': data.get('tls') == 'tls',
                'skip-cert-verify': True
            }

            net = data.get('net')
            if net == 'ws':
                proxy['network'] = 'ws'
                proxy['ws-opts'] = {'path': data.get('path', '/')}
                if data.get('host'):
                    proxy['ws-opts']['headers'] = {'Host': data.get('host')}
            elif net == 'grpc':
                proxy['network'] = 'grpc'
                proxy['grpc-opts'] = {'grpc-service-name': data.get('path', '')}

            if data.get('sni'):
                proxy['servername'] = data.get('sni')
            if data.get('fp'):
                proxy['client-fingerprint'] = data.get('fp')

            return proxy

        # ۳. TROJAN
        elif link.startswith('trojan://'):
            parsed = urllib.parse.urlparse(link)
            user_info = parsed.netloc.split('@')
            password = user_info[0]
            host_port = user_info[1].split(':')
            server = host_port[0]
            port = int(host_port[1])
            params = urllib.parse.parse_qs(parsed.query)
            remark = urllib.parse.unquote(parsed.fragment) or "Trojan"

            proxy = {
                'name': remark,
                'type': 'trojan',
                'server': server,
                'port': port,
                'password': password,
                'udp': True,
                'skip-cert-verify': True
            }

            if 'sni' in params:
                proxy['sni'] = params['sni'][0]

            net_type = params.get('type', [''])[0]
            if net_type == 'ws':
                proxy['network'] = 'ws'
                proxy['ws-opts'] = {'path': params.get('path', ['/'])[0]}
                if 'host' in params:
                    proxy['ws-opts']['headers'] = {'Host': params['host'][0]}
            elif net_type == 'grpc':
                proxy['network'] = 'grpc'
                proxy['grpc-opts'] = {'grpc-service-name': params.get('serviceName', [''])[0]}

            return proxy

        # ۴. SHADOWSOCKS
        elif link.startswith('ss://'):
            parsed = urllib.parse.urlparse(link)
            remark = urllib.parse.unquote(parsed.fragment) or "Shadowsocks"
            if '@' in parsed.netloc:
                user_info, host_port = parsed.netloc.split('@')
                decoded_user = safe_b64decode(user_info)
                cipher, password = decoded_user.split(':', 1)
                server, port = host_port.split(':')
            else:
                decoded = safe_b64decode(parsed.netloc)
                cipher_pass, host_port = decoded.split('@')
                cipher, password = cipher_pass.split(':', 1)
                server, port = host_port.split(':')

            return {
                'name': remark,
                'type': 'ss',
                'server': server,
                'port': int(port),
                'cipher': cipher,
                'password': password,
                'udp': True
            }

    except Exception as e:
        print(f"⚠️ ارور پارس لینک ({link[:30]}...): {e}")
    return None

# ==========================================
# ۱. پردازش RAW
# ==========================================
def process_raw(inputs, custom_name, repo_info):
    all_configs = []
    for item in inputs:
        content = fetch_or_read(item)
        extracted = extract_configs_from_text(content)
        all_configs.extend(extracted)

    if not all_configs:
        print("❌ هیچ کانفیگ معتبری یافت نشد!")
        return

    new_lines = []
    index = 1

    for line in all_configs:
        base_part = line.rsplit("#", 1)[0] if "#" in line else line
        new_title = urllib.parse.quote(f"{custom_name} {index:02d}")
        new_lines.append(f"{base_part}#{new_title}")
        index += 1

    result_text = "\n".join(new_lines)
    encoded_result = base64.b64encode(result_text.encode("utf-8")).decode("utf-8")

    filename = get_next_filename("sub-raw", "sub", ".txt")
    filepath = os.path.join("sub-raw", filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(encoded_result)

    print(f"✅ ساب RAW ساخته شد ({len(new_lines)} سرور): {filepath}")

    if repo_info:
        raw_url = f"https://raw.githubusercontent.com/{repo_info}/main/sub-raw/{filename}"
        qr_path = os.path.join("sub-raw", f"{os.path.splitext(filename)[0]}_qr.png")
        generate_qr(raw_url, qr_path)

# ==========================================
# ۲. پردازش CLASH
# ==========================================
def process_clash(inputs, custom_name, repo_info):
    all_proxies = []

    for item in inputs:
        content = fetch_or_read(item)
        decoded_content = safe_b64decode(content)
        
        # اگر مستقیم فایل YAML کلش بود
        if 'proxies:' in content or 'proxies:' in decoded_content:
            try:
                target_yaml = content if 'proxies:' in content else decoded_content
                data = yaml.safe_load(target_yaml)
                if isinstance(data, dict) and 'proxies' in data:
                    all_proxies.extend(data['proxies'])
            except Exception as e:
                print(f"⚠️ ارور در خواندن YAML کلش: {e}")
        else:
            extracted = extract_configs_from_text(content)
            for link in extracted:
                proxy = parse_uri_to_clash(link)
                if proxy:
                    all_proxies.append(proxy)

    if not all_proxies:
        print("❌ هیچ پروکسی معتبری پیدا نشد!")
        return

    index = 1
    proxy_names = []
    clean_proxies = []

    for proxy in all_proxies:
        if isinstance(proxy, dict):
            new_name = f"{custom_name} {index:02d}"
            proxy['name'] = new_name
            proxy_names.append(new_name)
            clean_proxies.append(proxy)
            index += 1

    clash_config = {
        'port': 7890,
        'socks-port': 7891,
        'allow-lan': True,
        'mode': 'rule',
        'log-level': 'info',
        'external-controller': '127.0.0.1:9090',
        'dns': {
            'enable': True,
            'enhanced-mode': 'fake-ip',
            'fake-ip-range': '198.18.0.1/16',
            'nameserver': [
                'https://1.1.1.1/dns-query',
                'https://dns.google/dns-query',
                '1.1.1.1',
                '8.8.8.8'
            ]
        },
        'proxies': clean_proxies,
        'proxy-groups': [
            {
                'name': custom_name,
                'type': 'select',
                'proxies': ['⚡ انتخاب خودکار'] + proxy_names
            },
            {
                'name': '⚡ انتخاب خودکار',
                'type': 'url-test',
                'proxies': proxy_names,
                'url': 'http://www.gstatic.com/generate_204',
                'interval': 300,
                'tolerance': 50
            }
        ],
        'rules': [
            'GEOIP,LAN,DIRECT',
            f'MATCH,{custom_name}'
        ]
    }

    filename = get_next_filename("sub-clash", "clash", ".yaml")
    filepath = os.path.join("sub-clash", filename)

    yaml_output = yaml.dump(clash_config, allow_unicode=True, sort_keys=False, default_flow_style=False)
    header_comments = f"# profile-title: {custom_name}\n\n"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(header_comments + yaml_output)

    print(f"✅ ساب Clash با موفقیت ساخته شد ({len(clean_proxies)} سرور): {filepath}")

    if repo_info:
        raw_url = f"https://raw.githubusercontent.com/{repo_info}/main/sub-clash/{filename}"
        qr_path = os.path.join("sub-clash", f"{os.path.splitext(filename)[0]}_qr.png")
        generate_qr(raw_url, qr_path)

# ==========================================
# ۳. پردازش JSON
# ==========================================
def process_json(inputs, custom_name, repo_info):
    all_outbounds = []

    for item in inputs:
        content = fetch_or_read(item)
        try:
            data = json.loads(content)
            outbounds = data.get("outbounds", []) if isinstance(data, dict) else data
            if isinstance(outbounds, list):
                all_outbounds.extend(outbounds)
        except Exception:
            pass

    if not all_outbounds:
        print("❌ هیچ داده JSON معتبری پیدا نشد!")
        return

    index = 1
    for item in all_outbounds:
        if isinstance(item, dict) and "tag" in item:
            item["tag"] = f"{custom_name} {index:02d}"
            index += 1

    final_json = {"remarks": custom_name, "outbounds": all_outbounds}

    filename = get_next_filename("sub-json", "json", ".json")
    filepath = os.path.join("sub-json", filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(final_json, f, ensure_ascii=False, indent=2)

    print(f"✅ ساب JSON جدید ساخته شد: {filepath}")

    if repo_info:
        raw_url = f"https://raw.githubusercontent.com/{repo_info}/main/sub-json/{filename}"
        qr_path = os.path.join("sub-json", f"{os.path.splitext(filename)[0]}_qr.png")
        generate_qr(raw_url, qr_path)

# ==========================================
# مدیریت اصلی ورودی‌ها
# ==========================================
if __name__ == "__main__":
    if len(sys.argv) > 3:
        sub_type = sys.argv[1].strip()
        raw_inputs = sys.argv[2].strip()
        base_name = sys.argv[3].strip()
        repo_info = sys.argv[4].strip() if len(sys.argv) > 4 else None

        # تفکیک خطوط یا فاصله‌ها
        inputs = [i.strip() for i in re.split(r"[\r\n]+", raw_inputs) if i.strip()]

        if "Raw" in sub_type or sub_type == "1":
            process_raw(inputs, base_name, repo_info)
        elif "Clash" in sub_type or sub_type == "2":
            process_clash(inputs, base_name, repo_info)
        elif "JSON" in sub_type or sub_type == "3":
            process_json(inputs, base_name, repo_info)
        else:
            print("❌ نوع ساب نامعتبر است!")
    else:
        print("❌ ورودی‌های کافی ارسال نشده است.")