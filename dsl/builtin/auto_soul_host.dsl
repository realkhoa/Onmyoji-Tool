loop forever {
  if exists('invite_by_default_checkbox.png') {
    find_and_click('invite_by_default_checkbox.png', 0.9)
    find_and_click('invite_by_default_ok_button.png', 0.9)
  } elif exists('soul_start.png') {
    find_and_click('soul_start.png', 0.9)
  } elif exists('realm_raid_reward_pot.png') {
    find_and_click('realm_raid_reward_pot.png', 0.9)
  } elif exists('realm_raid_fail.png') {
    find_and_click('realm_raid_fail.png', 0.9)
  }
  wait(1)
}