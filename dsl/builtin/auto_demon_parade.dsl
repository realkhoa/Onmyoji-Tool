loop forever
  if exists 'demon_parade_enter.png'
    find_and_click 'demon_parade_enter.png'
  elif exists 'demon_parade_title.png'
    find_and_click_largest_shiki
    wait_and_click 'demon_parade_start_button.png'
  elif exists 'demon_parade_got_bean.png'
    find_and_click 'demon_parade_got_bean.png'
    wait 0.5
  elif exists 'demon_parade_bean.png'
    find_and_click_largest_shiki
  elif exists 'demon_parade_result_title.png'
    find_and_click 'demon_parade_result_title.png'
  end
end