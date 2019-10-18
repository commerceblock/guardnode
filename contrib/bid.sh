#!/bin/bash
shopt -s expand_aliases

alias ocl="/Users/tomos/ocean/src/ocean-cli -datadir=$HOME/nodes/node1"

# Address tokens will be locked in
addr=`ocl getnewaddress`
pub=`ocl validateaddress $addr | jq -r ".pubkey"`

# Get asset unspent
unspent=`ocl listunspent 1 9999999 [] true "CBT" | jq .[0]`
asset_hash=`echo $unspent | jq -r ".asset"`
value=`echo $unspent | jq -r ".amount"`
txid=`echo $unspent | jq ".txid"`
vout=`echo $unspent | jq -r ".vout"`

# Fee
fee=0.001
# Current auction price
bid=10
# Change from unspent
change=$(echo "$value - $fee - $bid" | bc)

# Request id in service chain
requestid=fbf749977dcf7b1c09cca1d43855016c489b86e74137298ac985c1f01856a4e6
# Request end height
end=220
# Fee pubkey to pay fees in clientchain
feepub=03df51984d6b8b8b1cc693e239491f77a36c9e9dfe4a486e9972a18e03610a0d22

inputs="[{\"txid\":$txid,\"vout\":$vout,\"asset\":\"$asset_hash\"}]"
outputs="{\"endBlockHeight\":$end,\"requestTxid\":\"$requestid\",\"pubkey\":\"$pub\",\
\"feePubkey\":\"$feepub\",\"value\":$bid,\"change\":$change,\"changeAddress\":\"$addr\",\"fee\":$fee}"

signedtx=`ocl signrawtransaction $(ocl createrawbidtx $inputs $outputs)`
txidbid=`ocl sendrawtransaction $(echo $signedtx | jq -r ".hex")`
echo "txid: $txidbid"
