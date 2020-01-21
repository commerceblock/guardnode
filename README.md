# Guardnode

Guardnode daemon watches client blockchain and generates alerts for any errors or misbehaviour. In the event of a Coordinator challenge being made on the client chain the Guardnode daemon recognises it and a response is sent immediately.


## Instructions

### Running

1. `pip3 install -r requirements.txt`
2. `python3 setup.py build && python3 setup.py install`
3. Run `./run_guardnode` or `python3 -m guardnode` providing the required arguments:


### Configuration arguments

- `--rpchost`: Client RPC host
- `--rpcuser`: Client RPC username
- `--rpcpass`: Client RPC password
- `--servicerpchost`: Service RPC host
- `--servicerpcuser`: Service RPC username
- `--servicerpcpass`: Service RPC password
- `--serviceblocktime`: Service block time (Optional, defaults to 60)
- `--nodelogfile`: Node log file destination
- `--challengehost`: Challenge host address
- `--bidlimit`: Guardnode upper bid limit
- `--bidpubkey`: Guardnode winning bid public key (Optional, daemon will generate one)
- `--uniquebidpubkeys`: Flag to activate generation of fresh bid public keys for each bid (Optional)


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
