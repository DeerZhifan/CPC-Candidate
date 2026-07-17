(() => {
  const sections = [...document.querySelectorAll('details.sec')];
  const items = [...document.querySelectorAll('details.item')];
  if (!sections.length) return;

  const progress = document.createElement('div');
  progress.className = 'reading-progress';
  progress.setAttribute('aria-hidden', 'true');
  progress.innerHTML = '<span></span>';
  document.body.prepend(progress);
  const progressFill = progress.firstElementChild;
  const updateProgress = () => {
    const range = document.documentElement.scrollHeight - innerHeight;
    progressFill.style.width = `${range > 0 ? Math.min(100, scrollY / range * 100) : 100}%`;
  };
  addEventListener('scroll', updateProgress, { passive: true });
  addEventListener('resize', updateProgress, { passive: true });
  updateProgress();

  const firstSection = sections[0];
  const dashboard = document.createElement('div');
  dashboard.className = 'chapter-dashboard';
  dashboard.setAttribute('aria-label', '本章学习概览');
  const highFrequency = items.filter(item => (item.querySelector('.stars')?.textContent || '').length >= 4).length;
  dashboard.innerHTML = `
    <div class="chapter-metric"><strong>${sections.length}</strong><span>知识节</span></div>
    <div class="chapter-metric"><strong>${items.length}</strong><span>考点单元</span></div>
    <div class="chapter-metric"><strong>${highFrequency}</strong><span>四星以上</span></div>`;

  const controls = document.querySelector('.btns');
  (controls || firstSection).before(dashboard);

  const map = document.createElement('nav');
  map.className = 'section-map';
  map.setAttribute('aria-label', '本章小节导航');
  sections.forEach((section, index) => {
    const id = section.id || `section-${index + 1}`;
    section.id = id;
    const label = section.querySelector(':scope > summary')?.textContent.replace('▶', '').trim() || `第${index + 1}节`;
    const link = document.createElement('a');
    link.href = `#${id}`;
    link.textContent = label;
    link.addEventListener('click', () => { section.open = true; });
    map.append(link);
  });
  dashboard.after(map);

  document.querySelectorAll('.kp > b').forEach(label => label.classList.add('topic-label'));
  document.querySelectorAll('.kp table, .score table').forEach(table => {
    if (table.parentElement?.classList.contains('table-scroll')) return;
    const wrapper = document.createElement('div');
    wrapper.className = 'table-scroll';
    wrapper.setAttribute('role', 'region');
    wrapper.setAttribute('aria-label', '可横向滚动的数据表');
    wrapper.tabIndex = 0;
    table.before(wrapper);
    wrapper.append(table);
  });

  document.querySelectorAll('.btns button').forEach(button => {
    button.type = 'button';
  });
})();
