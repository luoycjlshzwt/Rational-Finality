#!/bin/bash
casetype=${1:-"1"}
caseduration=${2:-"7100"}

basedir=$(pwd)
casedir="${basedir}/case"
export BASEDIR="$basedir/"

# TOTAL_VALIDATORS=21504
# ATTACKER_COUNT=7526
# export ATTACKER_COUNT=$ATTACKER_COUNT

PYTHON=$(which python3)

updategenesis() {
        docker run -it --rm -v "${basedir}/config:/root/config" --entrypoint /usr/bin/prysmctl tscel/prysmctl:v5.2.0 \
                testnet \
                generate-genesis \
                --fork=deneb \
                --num-validators=16128 \
                --genesis-time-delay=15 \
                --output-ssz=/root/config/genesis.ssz \
                --chain-config-file=/root/config/config.yml \
                --geth-genesis-json-in=/root/config/genesis.json \
                --geth-genesis-json-out=/root/config/genesis.json
}
# 4356

testcase() {
  docase=$1
  targetdir="${casedir}/${docase}"
  resultdir="${basedir}/results/${docase}"

  if [ -d $resultdir ]; then
    # backup the resultdir
    echo "resultdir $resultdir exist, backup it to $resultdir-$(date +%Y%m%d%H%M%S)"
    mv $resultdir $resultdir-$(date +%Y%m%d%H%M%S)
  fi
  mkdir -p $resultdir
  echo "Running testcase $docase"
  updategenesis
  file=$casedir/attack-$docase.yml
  project=$docase
  docker compose -p $project-1 -f $file up -d
  echo "[*] Start the application layer verification script (running in the background)..."
  python3 app_impact_verify.py > "${resultdir}/app_impact_result.log" 2>&1 &
  
  echo "wait $caseduration seconds" && sleep $caseduration
  docker compose -p $project-1 -f $file down
  
  echo "result collect"
  sudo mv data $resultdir/data

  echo "test done and result in $resultdir"
#   echo "Experiment running... waiting $caseduration seconds"
#   sleep $caseduration
}

echo "Starting Rational Finality Attack Experiment..."

if [ "$casetype" == "14" ] || [ "$casetype" == "liveness" ]; then
    testcase liveness
fi
