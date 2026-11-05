import sys
import os
import time
import datetime
import urllib.request
import json
import random

# Force UTF-8 encoding
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import oci

def get_env(key, default=None):
    val = os.environ.get(key)
    if val is not None and str(val).strip():
        return str(val).strip()
    return default

# --- KONFIGURASI DARI ENVIRONMENT / DEFAULT ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

KEY_FILE_PATH = os.path.join(BASE_DIR, 'oci_api_key.pem')
key_content = get_env('OCI_KEY_CONTENT')
if key_content:
    with open(KEY_FILE_PATH, 'w', encoding='utf-8') as f:
        f.write(key_content.strip() + '\n')
elif not os.path.exists(KEY_FILE_PATH):
    for fname in os.listdir(BASE_DIR):
        if fname.endswith('.pem'):
            KEY_FILE_PATH = os.path.join(BASE_DIR, fname)
            break

SSH_PUB_KEY = get_env(
    'SSH_PUBLIC_KEY',
    'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFZJgQOuweYv/oGuPAWtPuARN2gpxhBaWoPZuRwQGaRL aduy.jabrik@gmail.com'
)

CONFIG = {
    'user': get_env('OCI_USER', 'ocid1.user.oc1..aaaaaaaaqfgbmbci47cbruocg6wxvqidxshn6tlm5sn33sqvpajhsrkpep4a'),
    'fingerprint': get_env('OCI_FINGERPRINT', '0f:7c:ec:97:5a:73:66:88:c2:3f:c7:df:15:35:ec:4e'),
    'tenancy': get_env('OCI_TENANCY', 'ocid1.tenancy.oc1..aaaaaaaang5wxjyleiulkgmtxxmhbeh3u3sn5vn4cxdqwlqr4mynogfvdnha'),
    'region': get_env('OCI_REGION', 'ap-batam-1'),
    'key_file': KEY_FILE_PATH
}

TARGET_BOOT_VOLUME_ID = get_env(
    'OCI_BOOT_VOLUME_ID',
    'ocid1.bootvolume.oc1.ap-batam-1.abrguljrxi4mladtxwzix2ax65km3irxph64q6v52tkuv5tl4e3eadx6afjq'
)
AVAILABILITY_DOMAIN = get_env('OCI_AD', 'WyvS:AP-BATAM-1-AD-1')
SUBNET_ID = get_env(
    'OCI_SUBNET_ID',
    'ocid1.subnet.oc1.ap-batam-1.aaaaaaaa2czequo4suud5b24gj7csh6kruqrythai7k6yjtsmxlgn5gcxgia'
)

OCPUS = float(get_env('OCI_OCPUS', '2.0'))
MEMORY_IN_GBS = float(get_env('OCI_RAM_GB', '12.0'))
DISPLAY_NAME = get_env('OCI_DISPLAY_NAME', 'acel-server-arm')

TELEGRAM_BOT_TOKEN = get_env('TELEGRAM_BOT_TOKEN', '8643508096:AAHTIJ_BMnxE4KEUdfVPQ9gYuJMQb1KT9-o')
TELEGRAM_CHAT_ID = get_env('TELEGRAM_CHAT_ID', '263504863')

MAX_RUN_MINUTES = int(get_env('MAX_RUN_MINUTES', '280')) # ~4.6 jam

def send_telegram(message):
    try:
        url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
        payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            pass
    except Exception as e:
        print(f"[!] Gagal kirim Telegram: {e}")

def main():
    print("=" * 60)
    print("[*] OCI AUTO-HUNTER CLOUD: RECOVERY SERVER ACEL (BATAM)")
    print(f"[*] Region   : {CONFIG['region']}")
    print(f"[*] Target   : {DISPLAY_NAME} ({OCPUS} OCPU, {MEMORY_IN_GBS} GB RAM)")
    print(f"[*] Max Run  : {MAX_RUN_MINUTES} menit")
    print("=" * 60)

    if not os.path.exists(KEY_FILE_PATH):
        print(f"[-] ERROR: Private key file tidak ditemukan di {KEY_FILE_PATH}")
        print("[-] Pastikan secret OCI_KEY_CONTENT sudah diatur di GitHub Secrets!")
        sys.exit(1)

    oci.config.validate_config(CONFIG)
    compute = oci.core.ComputeClient(CONFIG)
    virtual_net = oci.core.VirtualNetworkClient(CONFIG)

    # 1. Cek apakah server sudah aktif sebelumnya
    print("[*] Memeriksa status instance yang ada di Batam...")
    try:
        existing_instances = compute.list_instances(compartment_id=CONFIG['tenancy']).data
        for inst in existing_instances:
            if inst.display_name == DISPLAY_NAME and inst.lifecycle_state in ['RUNNING', 'PROVISIONING', 'STARTING']:
                print(f"[+] Instance {DISPLAY_NAME} sudah ada dan berstatus {inst.lifecycle_state}!")
                print("[+] Tidak perlu berburu lagi. Hunter selesai.")
                return
    except Exception as e:
        print(f"[!] Info cek instance: {e}")

    launch_details = oci.core.models.LaunchInstanceDetails(
        compartment_id=CONFIG['tenancy'],
        availability_domain=AVAILABILITY_DOMAIN,
        display_name=DISPLAY_NAME,
        shape='VM.Standard.A1.Flex',
        shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
            ocpus=OCPUS,
            memory_in_gbs=MEMORY_IN_GBS
        ),
        source_details=oci.core.models.InstanceSourceViaBootVolumeDetails(
            boot_volume_id=TARGET_BOOT_VOLUME_ID
        ),
        create_vnic_details=oci.core.models.CreateVnicDetails(
            subnet_id=SUBNET_ID,
            assign_public_ip=True
        ),
        metadata={
            'ssh_authorized_keys': SSH_PUB_KEY
        }
    )

    start_time = time.time()
    attempt = 1

    send_telegram(
        f"☁️ *OCI Hunter Berjalan di GitHub Actions Cloud!*\n\n"
        f"📍 *Region:* Batam (`ap-batam-1`)\n"
        f"🖥️ *Target:* `{DISPLAY_NAME}` ({int(OCPUS)} OCPU, {int(MEMORY_IN_GBS)} GB RAM)\n"
        f"🤖 Bot sekarang berburu 24/7 di Cloud. PC dan HP kamu bebas dimatikan!"
    )

    while True:
        elapsed_minutes = (time.time() - start_time) / 60.0
        if elapsed_minutes >= MAX_RUN_MINUTES:
            print(f"\n[*] Sesi {MAX_RUN_MINUTES} menit selesai. Bersiap untuk giliran jadwal berikutnya...")
            sys.exit(0)

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] [Percobaan #{attempt}] Mencoba meluncurkan instance...", end="", flush=True)

        try:
            res = compute.launch_instance(launch_details)
            instance = res.data
            print(" [OK] SUKSES BESAR!!")
            print(f"Instance ID: {instance.id}")
            print(f"State: {instance.lifecycle_state}")

            print("[*] Menunggu alokasi Public IP...")
            public_ip = "Sedang dialokasikan..."
            for _ in range(12):
                time.sleep(10)
                try:
                    vnics = compute.list_vnic_attachments(compartment_id=CONFIG['tenancy'], instance_id=instance.id).data
                    if vnics:
                        vnic = virtual_net.get_vnic(vnics[0].vnic_id).data
                        if vnic.public_ip:
                            public_ip = vnic.public_ip
                            break
                except Exception:
                    pass

            success_msg = (
                f"🎉🎉 *ALHAMDULILLAH! SERVER ACEL SUKSES HIDUP DARI CLOUD!* 🎉🎉\n\n"
                f"🖥️ *Nama:* `{instance.display_name}`\n"
                f"🌐 *Public IP:* `{public_ip}`\n"
                f"⚙️ *Spek:* {int(OCPUS)} OCPU, {int(MEMORY_IN_GBS)} GB RAM (GRATIS)\n"
                f"🔑 *SSH Command:*\n"
                f"`ssh -i oracle_ssh_key ubuntu@{public_ip}`\n\n"
                f"Harddisk ARM lama berhasil terpasang utuh! Server Acel sudah bangkit! 🚀"
            )
            print("\n" + "=" * 60)
            print(success_msg)
            print("=" * 60)
            send_telegram(success_msg)
            sys.exit(0)

        except oci.exceptions.ServiceError as e:
            if "Out of host capacity" in str(e.message) or e.status == 500:
                print(f" [WAIT] Kapasitas Batam masih penuh ({e.code}).")
                sleep_sec = random.randint(55, 75)
            elif e.status == 429:
                print(f" [WAIT] Terlalu cepat (Rate Limit 429). Istirahat sejenak...")
                sleep_sec = random.randint(70, 90)
            elif "QuotaExceeded" in str(e.message) or e.status == 400:
                print(f" [!] Quota Error: {e.message}")
                send_telegram(f"⚠️ *OCI Hunter Peringatan Quota:* {e.message}")
                sleep_sec = 60
            else:
                print(f" [!] Error ({e.status}): {e.message}")
                sleep_sec = 60
        except Exception as e:
            print(f" [!] Error: {e}")
            sleep_sec = 60

        attempt += 1
        time.sleep(sleep_sec)

if __name__ == '__main__':
    main()
