loop forever {
  if exists('guild_realm_raid_cooldown_noti.png', 0.5) {
    find_and_click('guild_realm_raid_scroll_icon.png', 0.8)
  } elif exists_exact('realm_raid_attack_button.png') {
    find_and_click('realm_raid_attack_button.png')
    wait(1)
  } elif exists('realm_raid_user_card.png') {
    find_and_click('realm_raid_user_card.png')
    wait_for('realm_raid_attack_button.png', 2)
  elif exists('realm_raid_reward_pot.png') {
    find_and_click('realm_raid_reward_pot.png')
  } elif exists('realm_raid_fail.png') {
    find_and_click('realm_raid_fail.png')
  } elif exists('realm_raid_title.png') and not exists('realm_raid_user_card.png') {
    drag_offset('guild_realm_raid_scroll_icon.png', 0, 50)
  }
  wait(0.25)
}