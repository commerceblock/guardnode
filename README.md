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
- `--bidtxid`: Guardnode winning bid txid
- `--pubkey`: Guardnode public key
- `--coordinator`: Coordinator host address
- `--challengeasset`: Challenge asset hash
- `--addressprefix`: Chain P2PKH address prefix

### Demo

To run a demo along with the [coordinator](https://github.com/commerceblock/coordinator) daemon execute the following replacing `$txid` with the txid produced by the coordinator [demo script](https://github.com/commerceblock/coordinator/scripts/demo.sh):

```bash
./run_guardnode --rpcuser user1 --rpcpassword password1 --pubkey 029aaa76fcf7b8012041c6b4375ad476408344d842000087aa93c5a33f65d50d92 --challengeasset 73be00507b15f79efccd0184b7ca8367372dfd5334ae8991a492f5f354073c88 --bidtxid $txid
```

### Docs

For more details check [readthedocs](https://commerceblock.readthedocs.io/en/latest/guardnode/index.html).
