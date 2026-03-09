# guild_realm_raid.dsl
# Tự động Phá kết giới guild (Guild Realm Raid)
# Chỉnh threshold nếu không nhận dạng được ảnh

loop forever
  if exists 'realm_raid_user_card.png' 0.85
    find_and_click 'realm_raid_user_card.png' 0.85
    wait_random 0.5 1.0
  elif exists 'realm_raid_attack_button.png' 0.85
    find_and_click 'realm_raid_attack_button.png' 0.85
    wait_random 0.5 1.0
  elif exists 'realm_raid_reward_pot.png' 0.85
    find_and_click 'realm_raid_reward_pot.png' 0.85
    wait_random 0.5 1.0
  else
    wait 1
  end
end
