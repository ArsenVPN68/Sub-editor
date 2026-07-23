import base64
import json
import os
import re
import socket
import urllib.parse
import urllib.request
import qrcode
import yaml

# ساخت پوشه‌های خروجی
for folder in ["sub-raw", "sub-clash", "sub-json"]:
    os.makedirs(folder, exist_ok=True)

def generate_qr(link, qr_filepath):
    try:
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
        qr.add_data(link)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(qr_filepath)
    except Exception as e:
        print(f"⚠️ QR Error: {e}")

def check_ping(host, port=443, timeout=2.0):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, int(port)))
        sock.close()
        return result == 0
    except Exception:
        return False

def safe_b64decode(s):
    if not s: return ""
    s = s.strip().replace("\r", "").replace("\n", "")
    missing_padding = len(s) % 4
    if missing_padding: s += '=' * (4 - missing_padding)
    try:
        return base64.b64decode(s).decode('utf-8', errors='ignore')
    except Exception:
        return s

def apply_clean_ip(link, clean_ip):
    if not clean_ip: return link
    try:
        if link.startswith(('vless://', 'vmess://', 'trojan://')):
            parsed = urllib.parse.urlparse(link)
            if '@' in parsed.netloc:
                user_info, host_port = parsed.netloc.split('@')
                port = host_port.split(':')[1] if ':' in host_port else '443'
                new_netloc = f"{user_info}@{clean_ip}:{port}"
                query = urllib.parse.parse_qs(parsed.query)
                if 'sni' not in query and ':' in host_port: query['sni'] = [host_port.split(':')[0]]
                if 'host' not in query and ':' in host_port: query['host'] = [host_port.split(':')[0]]
                return urllib.parse.urlunparse((parsed.scheme, new_netloc, parsed.path, parsed.params, urllib.parse.urlencode(query, doseq=True), parsed.fragment))
    except Exception: pass
    return link

def fetch_or_read(input_item):
    input_item = input_item.strip()
    if input_item.startswith(('http://', 'https://')):
        req = urllib.request.Request(input_item, headers={"User-Agent": "v2rayNG/1.8.12"})
        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                return response.read().decode("utf-8", errors="ignore")
        except Exception: return ""
    return input_item

def extract_configs_from_text(text, enable_ping=False, clean_ip=""):
    if not text: return []
    decoded = safe_b64decode(text)
    working_text = decoded if any(p in decoded for p in ["vless://", "vmess://", "trojan://", "ss://"]) else text
    pattern = r'(?:vless|vmess|trojan|ss|socks|hy2|tuic)://[^\s"#]+(?:#[^\s"]*)?'
    found = re.findall(pattern, working_text)
    
    final_list = []
    for cfg in found:
        if clean_ip: cfg = apply_clean_ip(cfg, clean_ip)
        if enable_ping:
            try:
                parsed = urllib.parse.urlparse(cfg)
                hp = parsed.netloc.split('@')[-1] if '@' in parsed.netloc else parsed.netloc
                host = hp.split(':')[0]
                port = hp.split(':')[1] if ':' in hp else 443
                if not check_ping(host, port):
                    print(f"❌ سرور قطعی فیلتر شد: {host}")
                    continue
            except Exception: pass
        final_list.append(cfg)
    return final_list

def remove_duplicates(configs):
    seen = set()
    unique = []
    for cfg in configs:
        base = cfg.rsplit("#", 1)[0] if "#" in cfg else cfg
        if base not in seen:
            seen.add(base)
            unique.append(cfg)
    return unique

def get_next_filename(folder_path, prefix="sub", extension=".txt"):
    count = 1
    while True:
        filename = f"{prefix}_{count}{extension}"
        if not os.path.exists(os.path.join(folder_path, filename)):
            return filename
        count += 1

def parse_uri_to_clash(link):
    """تبدیل URI به دیکشنری پروکسی Clash"""
    try:
        link = link.strip()
        if not link: return None

        if link.startswith('vless://'):
            parsed = urllib.parse.urlparse(link)
            user_info = parsed.netloc.split('@')
            uuid = user_info[0]
            host_port = user_info[1].split(':')
            params = urllib.parse.parse_qs(parsed.query)
            remark = urllib.parse.unquote(parsed.fragment) or "VLESS"
            security = params.get('security', [''])[0]
            net_type = params.get('type', [''])[0]

            proxy = {
                'name': remark, 'type': 'vless', 'server': host_port[0], 
                'port': int(host_port[1]), 'uuid': uuid, 'udp': True, 
                'tls': security in ['tls', 'reality'], 'skip-cert-verify': True
            }
            if security == 'reality':
                proxy['reality-opts'] = {'public-key': params.get('pbk', [''])[0]}
                if 'sid' in params: proxy['reality-opts']['short-id'] = params['sid'][0]
            if 'sni' in params: proxy['servername'] = params['sni'][0]
            if net_type == 'ws':
                proxy['network'] = 'ws'
                proxy['ws-opts'] = {'path': params.get('path', ['/'])[0]}
                if 'host' in params: proxy['ws-opts']['headers'] = {'Host': params['host'][0]}
            elif net_type == 'grpc':
                proxy['network'] = 'grpc'
                proxy['grpc-opts'] = {'grpc-service-name': params.get('serviceName', params.get('path', ['']))[0]}
            return proxy

        elif link.startswith('vmess://'):
            b64_part = link.replace('vmess://', '')
            data = json.loads(safe_b64decode(b64_part))
            proxy = {'name': data.get('ps', 'VMess'), 'type': 'vmess', 'server': data.get('add'), 'port': int(data.get('port', 443)), 'uuid': data.get('id'), 'alterId': int(data.get('aid', 0)), 'cipher': 'auto', 'udp': True, 'tls': data.get('tls') == 'tls', 'skip-cert-verify': True}
            net = data.get('net')
            if net == 'ws':
                proxy['network'] = 'ws'
                proxy['ws-opts'] = {'path': data.get('path', '/')}
                if data.get('host'): proxy['ws-opts']['headers'] = {'Host': data.get('host')}
            elif net == 'grpc':
                proxy['network'] = 'grpc'
                proxy['grpc-opts'] = {'grpc-service-name': data.get('path', '')}
            if data.get('sni'): proxy['servername'] = data.get('sni')
            return proxy
    except Exception: pass
    return None

def process_raw(inputs, custom_name, repo_info, enable_ping, clean_ip):
    all_configs = []
    for item in inputs:
        content = fetch_or_read(item)
        all_configs.extend(extract_configs_from_text(content, enable_ping, clean_ip))

    all_configs = remove_duplicates(all_configs)
    if not all_configs: return print("❌ هیچ کانفیگ معتبری یافت نشد!")

    new_lines = []
    for idx, line in enumerate(all_configs, 1):
        base_part = line.rsplit("#", 1)[0] if "#" in line else line
        new_lines.append(f"{base_part}#{urllib.parse.quote(f'{custom_name} {idx:02d}')}")

    filepath = os.path.join("sub-raw", get_next_filename("sub-raw", "sub", ".txt"))
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(base64.b64encode("\n".join(new_lines).encode("utf-8")).decode("utf-8"))

    if repo_info: generate_qr(f"https://raw.githubusercontent.com/{repo_info}/main/{filepath}", filepath.replace('.txt', '_qr.png'))
    print(f"✅ ساب RAW ساخته شد: {filepath}")

def process_clash(inputs, custom_name, repo_info, enable_ping, clean_ip):
    all_proxies = []
    for item in inputs:
        content = fetch_or_read(item)
        extracted_links = extract_configs_from_text(content, enable_ping, clean_ip)
        for link in remove_duplicates(extracted_links):
            proxy = parse_uri_to_clash(link)
            if proxy: all_proxies.append(proxy)

    if not all_proxies: return print("❌ هیچ پروکسی معتبری برای ساخت Clash پیدا نشد!")

    proxy_names = []
    clean_proxies = []
    for idx, proxy in enumerate(all_proxies, 1):
        if isinstance(proxy, dict):
            name = f"{custom_name} {idx:02d}"
            proxy['name'] = name
            proxy_names.append(name)
            clean_proxies.append(proxy)

    clash_config = {
        'port': 7890, 'socks-port': 7891, 'allow-lan': True, 'mode': 'rule', 'log-level': 'info',
        'dns': {'enable': True, 'enhanced-mode': 'fake-ip', 'nameserver': ['https://1.1.1.1/dns-query', '8.8.8.8']},
        'proxies': clean_proxies,
        'proxy-groups': [
            {'name': custom_name, 'type': 'select', 'proxies': ['⚡ انتخاب خودکار'] + proxy_names},
            {'name': '⚡ انتخاب خودکار', 'type': 'url-test', 'proxies': proxy_names, 'url': 'http://www.gstatic.com/generate_204', 'interval': 300}
        ],
        'rules': ['GEOIP,LAN,DIRECT', f'MATCH,{custom_name}']
    }

    filepath = os.path.join("sub-clash", get_next_filename("sub-clash", "clash", ".yaml"))
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# profile-title: {custom_name}\n\n" + yaml.dump(clash_config, allow_unicode=True, sort_keys=False))

    if repo_info: generate_qr(f"https://raw.githubusercontent.com/{repo_info}/main/{filepath}", filepath.replace('.yaml', '_qr.png'))
    print(f"✅ ساب Clash ساخته شد: {filepath}")

def process_json(inputs, custom_name, repo_info, enable_ping, clean_ip):
    all_outbounds = []
    for item in inputs:
        content = fetch_or_read(item)
        try:
            data = json.loads(content)
            outbounds = data.get("proxies", data.get("outbounds", []))
            if isinstance(outbounds, list): all_outbounds.extend(outbounds)
        except Exception: pass

    if not all_outbounds: return print("❌ هیچ داده JSON معتبری پیدا نشد!")

    for idx, item in enumerate(all_outbounds, 1):
        if isinstance(item, dict) and "name" in item: item["name"] = f"{custom_name} {idx:02d}"
        elif isinstance(item, dict) and "tag" in item: item["tag"] = f"{custom_name} {idx:02d}"

    filepath = os.path.join("sub-json", get_next_filename("sub-json", "json", ".json"))
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({"remarks": custom_name, "proxies": all_outbounds}, f, ensure_ascii=False, indent=2)

    if repo_info: generate_qr(f"https://raw.githubusercontent.com/{repo_info}/main/{filepath}", filepath.replace('.json', '_qr.png'))
    print(f"✅ ساب JSON ساخته شد: {filepath}")

if __name__ == "__main__":
    sub_type = os.getenv("SUB_TYPE", "").strip()
    raw_urls = os.getenv("INPUT_URLS", "").strip()
    base_name = os.getenv("CUSTOM_NAME", "ArsenVPN").strip()
    repo_info = os.getenv("REPO_INFO", "").strip()
    clean_ip = os.getenv("CLEAN_IP", "").strip()
    enable_ping = os.getenv("ENABLE_PING", "false").lower() == "true"

    inputs = [line.strip() for line in raw_urls.splitlines() if line.strip()]

    print(f"🔹 پردازش شروع شد - نوع: {sub_type} | تعداد: {len(inputs)} | آی‌پی تمیز: {clean_ip} | تست پینگ: {enable_ping}")

    # بررسی شرط بر اساس هر حالت ورود (بزرگ و کوچک بودن حروف رعایت شده)
    if "raw" in sub_type.lower() or sub_type == "1":
        process_raw(inputs, base_name, repo_info, enable_ping, clean_ip)
    elif "clash" in sub_type.lower() or sub_type == "2":
        process_clash(inputs, base_name, repo_info, enable_ping, clean_ip)
    elif "json" in sub_type.lower() or sub_type == "3":
        process_json(inputs, base_name, repo_info, enable_ping, clean_ip)
    else:
        print(f"❌ نوع ساب‌اسکریپشن نامشخص است: {sub_type}")