#!/bin/bash
shopt -s expand_aliases
alias ocl="$HOME/jsonrpc-cli/jsonrpc-cli --user=$RPC_USER --pass=$RPC_PASS --format=jsonpretty --resultonly=on --highlight=off  http://$RPC_CONNECT:$RPC_PORT/"

# parameters
# $1 genesisHash
# $2 feePubKey
# $3 fee
# Optional
# $4 maxBid
# $5 prevtxid
# $6 prevvout

# Check parameters are set
if [ -z $1 ] || [ -z $2 ] || [ -z $3 ]
then
    printf "%s\n" "createRequest genesisHash feePubKey fee maxBid ( txid ) ( vout )" \ \
    "Script builds, signs and sends a bid transaction to service chain for the request corresponding to the given client chain genesis hash." \
    "Set shell enviroment variables RPC_CONNECT, RPC_PORT, RPC_USER, RPC_PASS with network connection information." \
    "By deflault a TX_LOCKED_MULTISIG transaction or standard domain asset unspent output funds the bid. If a specific transaction should be used then set parameters 5 and 6 accordingly." \
    \ \
    "Arguments:" \
    "1. \"genesisHash\"        (Amount, Required) Client chain genesis hash" \
    "2. \"feePubKey\"          (Integer, Required) Public key to pay fees on client chain" \
    "3. \"fee\"                (Integer, Required) Value of bid transaction fee" \
    "4. \"maxBid\"             (Amount, Required) Maximum amount willing to bid or 'false' if no maximum bid cut-off desired"
    "5. \"txid\"               (String (hex), Optional) Specified previous request transaction ID to fund new bid" \
    "6. \"vout\"               (Integer, Optional) Specified previous request vout to fund new bid"
    \ \
    "Result: " \
    "\"txid\"                    (hex string) Transaction ID of bid transaction"
    exit
fi

# Client chain genesis block hash
genesis=$1
# check for currently active request for given genesis hash
request=`ocl getrequests '["'$genesis'", true]' | jq '.[]'`
if [[ -z $request ]]
then
    printf "Input parameter error: No in auction requests with genesis block hash provided.\n\n"
    exit
fi

# Get current auction price
bid=`echo $request | jq ".auctionPrice"`
if [[ $4 =~ ^[+-]?[0-9]+\.?[0-9]*$ ]]; then # maxBid existence and type check
maxbid=$4
elif [ ! $4 = false ]; then
    printf "Input parameter error: Invalid maxBid value given.\n"
    exit
fi
if (( $(echo "$bid > $maxbid" | bc -l) )); then
    printf "Max bid error: Current bid price larger than maxBid.\n"
    exit
fi

# Address tokens will be locked in
addr=`ocl getnewaddress | jq -r '.'`
pub=`ocl validateaddress $addr | jq -r ".pubkey"`
# Request id in service chain
requestid=`echo $request | jq -r '.txid'`
# Request end height
end=`echo $request | jq '.endBlockHeight'`
# Fee pubkey to pay fees in client chain
feepub=$2
# Fee value
fee=$3

currentblockheight=`ocl getblockchaininfo | jq ".blocks"`
checkLockTime () {
    if [[ $currentblockheight -gt `echo $1 | jq -r '.locktime'` ]]; then
        return 0
    fi
    return 1
}
calculateChange () {  # receive value of unspent as arg
    change=$(echo "$1 - $fee - $bid" | bc)
    if [[ $change < 0 ]]; then
        return
    fi
    echo $change
}
# Check for specified locked bid transaction info and set txid, vout variables accordingly
if [ -n "$5" ] || [ -n "$6" ]
then
    if [ -z $5 ] || [ -z $6 ]; then
        printf "Input parameter error: txid and vout must be provided for locked bid transaction output.\n"
        exit
    fi
    txid=$5
    vout=$6
    tx=`ocl decoderawtransaction $(ocl getrawtransaction $txid | jq -r '.')`
    if checkLockTime "$tx"; then
        assethash=`echo $tx | jq -r '.vout['$vout'].asset'`
        value=`echo $tx | jq -r '.vout['$vout'].value'`
        change=$(calculateChange "$value")
        if [ -z $change ]; then
            printf "Input error: Input transaction not large enough to fund bid+fee.\n"
            exit
        fi
    else
        printf "Input parameter error: Previous bid transaction nlocktime not met.\n"
        exit
    fi
else
    unspentlist=`ocl listunspent '[1, 9999999, [], true, "CBT"]' | jq -c '.[]'`
    # Try find TX_LOCKED_MULTISIG to spend from first
    for unspent in $unspentlist; do
        if [ `echo $unspent | jq ".solvable"` = "false" ]; then
            value=`echo $unspent | jq -r ".amount"`
            change=$(calculateChange "$value")
            txid=`echo $unspent | jq -r ".txid"`
            vout=`echo $unspent | jq -r ".vout"`
            tx=`ocl decoderawtransaction $(ocl getrawtransaction $txid | jq -r '.')`
            if [ ! -z $change ] && checkLockTime "$tx"; then
                assethash=`echo $unspent | jq -r ".asset"`
                break
            fi
        fi
    done
    # Try find standard domain asset unpsent output to fund bid
    if [ -z $assethash ]; then
        for unspent in $unspentlist; do
            value=`echo $unspent | jq -r ".amount"`
            change=$(calculateChange "$value")
            txid=`echo $unspent | jq -r ".txid"`
            vout=`echo $unspent | jq -r ".vout"`
            tx=`ocl decoderawtransaction $(ocl getrawtransaction $txid | jq -r '.')`
            if [ ! -z $change ] && checkLockTime "$tx"; then
                assethash=`echo $unspent | jq -r ".asset"`
                break
            fi
        done
    fi
    if [ -z $change ]; then
        printf "Input error: No unpsent outputs large enough to fund bid+fee.\n"
        exit
    fi
fi

inputs="[{\"txid\":\"$txid\",\"vout\":$vout,\"asset\":\"$assethash\"}]"
outputs="{\"endBlockHeight\":$end,\"requestTxid\":\"$requestid\",\"pubkey\":\"$pub\",\
\"feePubkey\":\"$feepub\",\"value\":$bid,\"change\":$change,\"changeAddress\":\"$addr\",\"fee\":$fee}"

echo "Creating bid on request with txid:" $requestid
rawtx=`ocl createrawbidtx '['$(echo $inputs)','$(echo $outputs)']' | jq -r '.'`
signedrawtx=`ocl signrawtransaction $rawtx`
# Catch signing error
if [ `echo $signedrawtx | jq ".complete"` = "false" ]
then
    printf "Signing error: Script cannot be signed. Is the input transaction information correct and is it unlockable now?"
fi

txidbid=`ocl sendrawtransaction $(echo $signedrawtx | jq -r ".hex") | jq -r '.'`
echo "Bid txid:" $txidbid

# Import spending address to allow script to automatically update request
address=`ocl decoderawtransaction $(echo $signedrawtx | jq -r '.hex') | jq -r '.vout[0].scriptPubKey.hex'`
ocl importaddress $address > /dev/null
