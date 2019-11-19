# Guardnode

Guardnode daemon responding to client chain coordinator challenges and generating alerts for misbehaviour on the chain.


## Instructions

### Running

1. `pip3 install -r requirements.txt`
2. `python3 setup.py build && python3 setup.py install`
3. Run `./run_guardnode` or `python3 -m guardnode` providing the required arguments:


### Configuration arguments

- `--rpcconnect`: Client RPC host
- `--rpcport`: Client RPC port
- `--rpcuser`: Client RPC username
- `--rpcpassword`: Client RPC password
- `--nodeaddrprefix`: Node P2PKH address prefix
- `--nodelogfile`: Node log file destination
- `--bidtxid`: Guardnode winning bid txid
- `--bidpubkey`: Guardnode winning bid public key
- `--challengehost`: Challenge host address


### Running services with docker-compose

Clone data directories

```console
git clone https://github.com/commerceblock/guardnode.git \
 && cd guardnode
```

Start ocean node:

```console
docker-compose \
    -p ocean \
    -f contrib/docker-compose/cb-guardnode-testnet.yml \
    up -d ocean
```

Start guardnode:

```console
docker-compose \
    -p ocean \
    -f contrib/docker-compose/cb-guardnode-testnet.yml \
    up -d guardnode
```

Check status:

```console
docker-compose \
    -p ocean \
    -f contrib/docker-compose/cb-guardnode-testnet.yml \
    ps
```

Check ocean logs:

```console
docker-compose \
    -p ocean \
    -f contrib/docker-compose/cb-guardnode-testnet.yml \
    logs --follow ocean
```

Check guarnode logs:

```console
docker-compose \
    -p ocean \
    -f contrib/docker-compose/cb-guardnode-testnet.yml \
    logs --follow guardnode
```

### Docs

For more details and a demo check the [guardnode guide](https://commerceblock.readthedocs.io/en/latest/guardnode-guide/index.html).
