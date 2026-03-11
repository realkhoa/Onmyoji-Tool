loop forever {
  if exists('soul_join_by_default_button.png') {
    find_and_click('soul_join_by_default_button.png', 0.9)
  } elif exists('realm_raid_reward_pot.png') {
    find_and_click('realm_raid_reward_pot.png', 0.9)
  } elif exists('realm_raid_fail.png') {
    find_and_click('realm_raid_fail.png', 0.9)
  } elif exists('battle_victory_drum.png') {
    find_and_click('battle_victory_drum.png', 0.9)
  }
  wait(1)
}