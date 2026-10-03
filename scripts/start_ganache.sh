#!/usr/bin/env bash
# Starts a local Ganache blockchain on http://127.0.0.1:8545
# Fixed mnemonic so we always get the same 10 accounts (100 ETH each).
# Account 0 = deployer, 1 = hotel, 2 = guest, 3 = second guest

MNEMONIC="test test test test test test test test test test test junk"

if command -v ganache >/dev/null 2>&1; then
  GANACHE="ganache"
else
  GANACHE="npx --yes ganache@7"
fi

echo "Starting Ganache (chain id 1337, port 8545)..."
$GANACHE \
  --wallet.mnemonic "$MNEMONIC" \
  --wallet.totalAccounts 10 \
  --wallet.defaultBalance 100 \
  --chain.chainId 1337 \
  --chain.hardfork shanghai \
  --server.port 8545