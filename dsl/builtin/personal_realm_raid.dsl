loop forever
  if exists 'realm_raid_reward_pot.png'
    find_and_click 'realm_raid_reward_pot.png'
  elif exists 'realm_raid_fail.png'
    find_and_click 'realm_raid_fail.png'
  elif exists 'realm_raid_attack_button.png'
    find_and_click 'realm_raid_attack_button.png'
  elif exists_exact 'realm_raid_user_card.png'
    find_and_click 'realm_raid_user_card.png'
  elif not exists_exact 'realm_raid_user_card.png'
    if exists 'realm_raid_title.png'
      wait_and_click 'realm_raid_reload.png'
      wait_and_click 'realm_raid_reset_ok_button.png'
    end
  end

  wait 1
end