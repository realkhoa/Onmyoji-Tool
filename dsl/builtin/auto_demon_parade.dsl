binding $threshole number 0.8

if exists('demon_parade_bean.png') {
  throw_at_largest_shiki()
} else {
  if exists('demon_parade_start_button.png') {
    find_and_click_largest_shiki()
  } else {
    find_and_click('demon_parade_enter.png', $threshole)
    find_and_click('demon_parade_start_button.png')
    drag_offset('demon_parade_bean_slider_5.png', 400, 0)
    find_and_click('demon_parade_result_title.png', $threshole)
  }
}