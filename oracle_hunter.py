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

DISPLAY_NAME = get_env('OCI_DISPLAY_NAME', 'acel-server-arm')

# 3 Rak Server Fisik Terpisah di Data Center Batam
FAULT_DOMAINS = [
    'FAULT-DOMAIN-1',
    'FAULT-DOMAIN-2',
    'FAULT-DOMAIN-3'
]

# 3 Prioritas Spek (3 spek x 3 FD = 9 kombinasi, pas di bawah batas API 10 item!)
# Diurutkan dari spek paling ideal ke remah terkecil.
RADAR_SPECS = [
    {"ocpus": 2.0, "ram": 12.0, "label": "2 OCPU / 12 GB RAM (Target Utama)"},
    {"ocpus": 1.0, "ram": 6.0,  "label": "1 OCPU / 6 GB RAM (Celah Cepat)"},
    {"ocpus": 1.0, "ram": 2.0,  "label": "1 OCPU / 2 GB RAM (Remah Mikro)"},
]

TELEGRAM_BOT_TOKEN = get_env('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = get_env('TELEGRAM_CHAT_ID', '263504863')

MAX_RUN_MINUTES = int(get_env('MAX_RUN_MINUTES', '330')) # ~5.5 jam

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN:
        return
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

def try_launch(compute, virtual_net, launch_details, fd, ocpus, ram, reason="Sniper"):
    """Mencoba meluncurkan instance ke Fault Domain dan spek tertentu."""
    launch_details.shape_config.ocpus = ocpus
    launch_details.shape_config.memory_in_gbs = ram
    launch_details.fault_domain = fd

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] 🎯 [{reason}] Menembak {fd} ({int(ocpus)} OCPU / {int(ram)} GB RAM)...", end="", flush=True)

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
            f"⚙️ *Spek Berhasil:* {int(ocpus)} OCPU, {int(ram)} GB RAM di `{fd}` (GRATIS Always Free)\n"
            f"🔑 *SSH Command:*\n"
            f"`ssh -i oracle_ssh_key ubuntu@{public_ip}`\n\n"
            f"Harddisk ARM lama berhasil terpasang utuh! Server Acel sudah bangkit! 🚀\n"
            f"*(Catatan: Jika spek masih 1 OCPU / 2 GB, kita bisa langsung scale-up ke 2 OCPU / 12 GB kapan saja lewat Oracle Console!)*"
        )
        print("\n" + "=" * 60)
        print(success_msg)
        print("=" * 60)
        send_telegram(success_msg)
        return True, 0

    except oci.exceptions.ServiceError as e:
        if "Out of host capacity" in str(e.message) or e.status == 500:
            print(f" [WAIT] Penuh ({e.code}).")
            return False, 0
        elif e.status == 429:
            print(" [WAIT] Rate Limit 429 pada launch_instance.")
            return False, 429
        elif "QuotaExceeded" in str(e.message) or e.status == 400:
            print(f" [!] Quota/Param Error: {e.message}")
            return False, 400
        else:
            print(f" [!] Error ({e.status}): {e.message}")
            return False, e.status
    except Exception as e:
        print(f" [!] Error: {e}")
        return False, -1

def main():
    print("=" * 65)
    print("[*] OCI RADAR + SNIPER v3: RECOVERY SERVER ACEL (BATAM)")
    print(f"[*] Region   : {CONFIG['region']}")
    print(f"[*] Target   : {DISPLAY_NAME} (9-Slot Capacity Radar + Direct Sniper)")
    print(f"[*] Max Run  : {MAX_RUN_MINUTES} menit")
    print("=" * 65)

    if not os.path.exists(KEY_FILE_PATH):
        print(f"[-] ERROR: Private key file tidak ditemukan di {KEY_FILE_PATH}")
        sys.exit(1)

    oci.config.validate_config(CONFIG)
    compute = oci.core.ComputeClient(CONFIG, timeout=(15.0, 20.0))
    virtual_net = oci.core.VirtualNetworkClient(CONFIG, timeout=(15.0, 20.0))

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

    # Siapkan detail peluncuran
    launch_details = oci.core.models.LaunchInstanceDetails(
        compartment_id=CONFIG['tenancy'],
        availability_domain=AVAILABILITY_DOMAIN,
        display_name=DISPLAY_NAME,
        shape='VM.Standard.A1.Flex',
        shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
            ocpus=2.0,
            memory_in_gbs=12.0
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

    # Siapkan detail Capacity Radar (9 Kombinasi sekaligus dalam 1 API call!)
    shapes_to_check = []
    for spec in RADAR_SPECS:
        for fd in FAULT_DOMAINS:
            shapes_to_check.append(
                oci.core.models.CreateCapacityReportShapeAvailabilityDetails(
                    instance_shape='VM.Standard.A1.Flex',
                    fault_domain=fd,
                    instance_shape_config=oci.core.models.CapacityReportInstanceShapeConfig(
                        ocpus=spec["ocpus"],
                        memory_in_gbs=spec["ram"]
                    )
                )
            )

    radar_details = oci.core.models.CreateComputeCapacityReportDetails(
        compartment_id=CONFIG['tenancy'],
        availability_domain=AVAILABILITY_DOMAIN,
        shape_availabilities=shapes_to_check
    )

    start_time = time.time()
    scan_count = 1
    probe_index = 0

    send_telegram(
        f"📡 *OCI RADAR + SNIPER v3 Aktif di Cloud!*\n\n"
        f"📍 *Region:* Batam (`ap-batam-1`)\n"
        f"🔍 *Radar:* Memindai 9 slot sekaligus setiap ~8 detik (3 Rak Fisik x 3 Spek)\n"
        f"🎯 *Target:* `2 Core 12GB` > `1 Core 6GB` > `1 Core 2GB`\n"
        f"⚡ Kecepatan deteksi naik 60x lipat tanpa terkena 429!"
    )

    while True:
        elapsed_minutes = (time.time() - start_time) / 60.0
        if elapsed_minutes >= MAX_RUN_MINUTES:
            print(f"\n[*] Sesi {MAX_RUN_MINUTES} menit selesai ({scan_count - 1} radar scan = {(scan_count - 1) * 9} pengecekan slot).")
            continue_flag_path = os.path.join(os.environ.get('RUNNER_TEMP', '/tmp'), 'hunter_continue')
            try:
                with open(continue_flag_path, 'w', encoding='utf-8') as f:
                    f.write('CONTINUE')
            except Exception as e:
                print(f"[!] Info flag continue: {e}")
            sys.exit(0)

        # Langkah A: Jalankan Radar (cek 9 kombinasi sekaligus tanpa limit!)
        radar_hit = None
        try:
            rep = compute.create_compute_capacity_report(radar_details).data
            for sa in rep.shape_availabilities:
                if sa.availability_status == 'AVAILABLE':
                    radar_hit = sa
                    break

            if radar_hit:
                hit_ocpus = radar_hit.instance_shape_config.ocpus
                hit_ram = radar_hit.instance_shape_config.memory_in_gbs
                hit_fd = radar_hit.fault_domain
                print(f"\n🚨 [RADAR HIT!!] Slot {hit_fd} ({int(hit_ocpus)} OCPU / {int(hit_ram)} GB) TERSEDIA! Menembak seketika!")
                ok, _ = try_launch(compute, virtual_net, launch_details, hit_fd, hit_ocpus, hit_ram, reason="RADAR-LOCK")
                if ok:
                    sys.exit(0)
            else:
                # Print heartbeat log setiap 15 scan (~2 menit sekali) agar log tetap rapi
                if scan_count == 1 or scan_count % 15 == 0:
                    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"[{now}] [Radar Scan #{scan_count}] 9/9 kombinasi Batam terpantau penuh. Memantau setiap ~8 detik...")

        except oci.exceptions.ServiceError as e:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if e.status == 429:
                print(f"[{now}] [Radar Scan #{scan_count}] Rate limit radar 429, istirahat 25 detik...")
                time.sleep(25)
            else:
                print(f"[{now}] [Radar Scan #{scan_count}] Radar error ({e.status}): {e.message}")
        except Exception as e:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}] [Radar Scan #{scan_count}] Radar exception: {e}")

        # Langkah B: Tembakan verifikasi langsung tiap 45 scan (~6 menit sekali)
        if scan_count % 45 == 0:
            spec = RADAR_SPECS[probe_index % len(RADAR_SPECS)]
            fd = FAULT_DOMAINS[probe_index % len(FAULT_DOMAINS)]
            ok, _ = try_launch(compute, virtual_net, launch_details, fd, spec["ocpus"], spec["ram"], reason="Heartbeat-Probe")
            if ok:
                sys.exit(0)
            probe_index += 1

        scan_count += 1
        time.sleep(random.randint(7, 10))

if __name__ == '__main__':
    main()
