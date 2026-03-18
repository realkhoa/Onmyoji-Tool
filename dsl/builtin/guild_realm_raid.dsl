binding $threshole number 0.8
binding $slide_offset slider 10

if exists('guild_realm_raid_cooldown_noti.png', 0.6) {
  find_and_click('guild_realm_raid_scroll_icon.png', $threshole)
} elif exists_exact('realm_raid_attack_button.png', $threshole) {
  find_and_click('realm_raid_attack_button.png', $threshole)
  wait(1)
} elif exists('realm_raid_user_card.png', $threshole) {
  find_and_click('realm_raid_user_card.png', $threshole)
  wait_for('realm_raid_attack_button.png', 2)
} elif exists('realm_raid_reward_pot.png', $threshole) {
  find_and_click('realm_raid_reward_pot.png', $threshole)
} elif exists('realm_raid_fail.png', $threshole) {
  find_and_click('realm_raid_fail.png', $threshole)
} elif exists('realm_raid_title.png', $threshole) and not exists('realm_raid_user_card.png', $threshole) {
  drag_offset('guild_realm_raid_scroll_icon.png', 0, $slide_offset)
}
wait(0.25)
