# Journal

This is a python script destined to scrap packet data from an deobfuscated minecraft server jar file. (1.20.6)

The project use [lawu](https://github.com/TkTech/Lawu) python package to inspect the jar file and extract the packet data and is inspired by the [Burger](https://github.com/Pokechu22/Burger) project (which is not working with deobfuscated jar).

## How to use

1. Install the required packages

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Run the script

```bash
python3 article.py -j <path to the jar file>
```

## Getting the jar file

You can get any deobfuscated minecraft server jar file with the [MinecraftDecompiler](https://github.com/MaxPixelStudios/MinecraftDecompiler) tool.

1. Download the latest release from the [releases page](https://github.com/MaxPixelStudios/MinecraftDecompiler/releases)

2. Run the tool with the following command

```bash
java -jar <MinecraftDecompiler jar> -v "1.20.6" -s "SERVER"
```

The deobfuscated jar file will be in the `output` folder.

## Features

Retrieve most packet (missing 'custom_payload' ones) and some information about them.

```json
{
    "id": -1,
    "name": "BLOCK_ENTITY_TAG_QUERY",
    "side": "SERVERBOUND",
    "state": "game",
    "class": "net/minecraft/network/protocol/game/ServerboundBlockEntityTagQueryPacket",
    "structure": {
        "transactionId": "VarInt",
        "pos": "BlockPos"
    }
},
```

The `structure` field is not working for all packets, but it's a work in progress.

We are currently missing the ids until I find a way to get them from the jar file.
