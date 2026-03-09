set fail = 0

loop forever
  count fail 'realm_raid_failure.png'
  if fail > 0
    wait_and_click 'realm_raid_reload.png'
    wait_and_click 'realm_raid_reset_ok_button.png'
  elif exists 'realm_raid_reward_pot.png'
    find_and_click 'realm_raid_reward_pot.png'
  elif exists 'realm_raid_attack_button.png'
    find_and_click 'realm_raid_attack_button.png'
  elif exists 'realm_raid_user_card.png'
    find_and_click 'realm_raid_user_card.png'
  elif exists 'realm_raid_fail.png'
    find_and_click 'realm_raid_fail.png'
  end

  wait 1
end