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

### Demo

The following is a tutorial to see the Guardnode in action without having to run a coordinator instance. First run the coordinator [demo script](https://github.com/commerceblock/coordinator/blob/master/scripts/demo.sh) which generates a request and bid on for that request on a mock service chain.

Next, in a separate terminal window, execute the following replacing `$txid` with a bid txid produced by the demo script above.

```bash
./run_guardnode --rpcuser user1 --rpcpassword password1 --bidpubkey 029aaa76fcf7b8012041c6b4375ad476408344d842000087aa93c5a33f65d50d92 --nodelogfile $HOME/co-client-dir/ocean_test/debug.log --bidtxid $txid
```
We can now send a CHALLENGE asset transaction and watch the guardnode react. In the first terminal window execute:

```bash
alias ocn='/$HOME/ocean/src/ocean-cli -datadir=$HOME/co-client-dir'

ocn sendtoaddress $(ocn getnewaddress) 1 "" "" false "CHALLENGE"

ocn generate 1
```

As there is no connection to a coordinator we get an error message but the would-be message is displayed. Guardnode sends their bid txid to identify themselves, the challenge tx hash and a signature to coordinator as a response to the challenge and thus prove their active watching of the client chain.

### Demo with coordinator

To run a demo along with the [coordinator](https://github.com/commerceblock/coordinator) daemon execute the following replacing `$txid` with the txid produced by the coordinator [demo script](https://github.com/commerceblock/coordinator/blob/master/scripts/demo.sh):

```bash
./run_guardnode --rpcuser user1 --rpcpassword password1 --bidpubkey 029aaa76fcf7b8012041c6b4375ad476408344d842000087aa93c5a33f65d50d92 --nodelogfile $HOME/co-client-dir/ocean_test/debug.log --bidtxid $txid
```
This time the coordinator receives the message
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

For more details check the [guardnode guide](https://commerceblock.readthedocs.io/en/latest/guardnode-guide/index.html).
