# Guardnode

Guardnode daemon responding to client chain coordinator challenges and generating alerts for misbehavior on the chain.

## Instructions

### Running

1. `pip3 install -r requirements.txt`
2. `python3 setup.py build && python3 setup.py install`
3. Run `./run_guardnode` or `python3 -m guardnode` providing the arguments required

### Congifuration arguments

- `--rpcconnect`: Client RPC host
- `--rpcport`: Client RPC port
- `--rpcuser`: Client RPC username
- `--rpcpassword`: Client RPC password
- `--nodeaddrprefix`: Node P2PKH address prefix
- `--nodelogfile`: Node log file destination
- `--bidtxid`: Guardnode winning bid txid
- `--bidpubkey`: Guardnode winning bid public key
- `--challengehost`: Challenge host address
- `--challengeasset`: Challenge asset hash

### Demo

To run a demo along with the [coordinator](https://github.com/commerceblock/coordinator) daemon execute the following replacing `$txid` with the txid produced by the coordinator [demo script](https://github.com/commerceblock/coordinator/scripts/demo.sh):

```bash
./run_guardnode --rpcuser user1 --rpcpassword password1 --bidpubkey 029aaa76fcf7b8012041c6b4375ad476408344d842000087aa93c5a33f65d50d92 --challengeasset 73be00507b15f79efccd0184b7ca8367372dfd5334ae8991a492f5f354073c88 --bidtxid $txid
```

### Running services with docker-compose

To run all all services defined in a docker-compose.yml file run

`docker-compose up`

in the directory where the file is.

To only run the guardnode service use:

`docker-compose up -d guardnode`

To follow the logs use:

`docker-compose logs --follow guardnode`

For just oceand use:

`docker-compose up -d ocean`

For different docker compose files names specify the filename with the `-f` flag.

### Docs

For more details check the [guardnode guide](https://commerceblock.readthedocs.io/en/latest/guardnode-guide/index.html).
