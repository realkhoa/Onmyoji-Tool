loop forever
  if exists 'demon_parade_enter.png'
    find_and_click 'demon_parade_enter.png'
  elif exists 'demon_parade_title.png'
    find_and_click_largest_shiki
    wait 1
    wait_and_click 'demon_parade_start_button.png'
    wait_for 'demon_parade_bean_slider_5.png'
    drag_offset 'demon_parade_bean_slider_5.png' 400 0
  elif exists 'demon_parade_bean.png'
    throw_at_largest_shiki
  elif exists 'demon_parade_result_title.png'
    find_and_click 'demon_parade_result_title.png'
  end
end