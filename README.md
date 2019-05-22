# Guardnode

Guardnode daemon responding to coordinator challenges and generating alerts.

## Instructions
1. `pip3 install -r requirements.txt`
2. `python3 setup.py build && python3 setup.py install`
3. Run `./run_guardnode` or `python3 -m guardnode` providing the arguments required

Arguments:

- `--rpcconnect`: Client RPC host
- `--rpcport`: Client RPC port
- `--rpcuser`: Client RPC username
- `--rpcpassword`: Client RPC password
- `--bidtxid`: Guardnode winning bid txid
- `--pubkey`: Guardnode public key
- `--coordinator`: Coordinator host address
- `--challengeasset`: Challenge asset hash
- `--addressprefix`: Chain P2PKH address prefix
