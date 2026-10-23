
(function(){
  var pages=[].slice.call(document.querySelectorAll('.page'));
  if(!pages.length) return;
  var reduce=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var bar=document.querySelector('.progress i');
  var now=document.getElementById('now-page');
  function cur(){
    var best=1,bd=Infinity;
    pages.forEach(function(p,i){
      var d=Math.abs(p.getBoundingClientRect().top-72);
      if(d<bd){bd=d;best=i;}
    });
    return best;
  }
  function go(i){
    i=Math.max(0,Math.min(pages.length-1,i));
    pages[i].scrollIntoView({behavior:reduce?'auto':'smooth',block:'start'});
    history.replaceState(null,'','#p'+(i+1));
  }
  function sync(){
    var i=cur();
    if(now) now.textContent=String(i+1).padStart(2,'0')+' / '+String(pages.length).padStart(2,'0');
    if(bar){
      var h=document.documentElement.scrollHeight-window.innerHeight;
      bar.style.width=(h>0?Math.min(100,Math.max(0,window.scrollY/h*100)):0)+'%';
    }
  }
  window.addEventListener('scroll',sync,{passive:true});
  window.addEventListener('resize',sync);
  sync();
  document.addEventListener('keydown',function(e){
    if(e.metaKey||e.ctrlKey||e.altKey) return;
    var t=e.target||{};
    if(/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName||'')) return;
    var overlay=document.getElementById('index');
    if(e.key==='Escape'){ if(overlay) overlay.classList.toggle('show'); return; }
    if(overlay&&overlay.classList.contains('show')) return;
    if(e.key==='ArrowRight'||e.key==='ArrowDown'||e.key==='PageDown'||e.key===' '){ e.preventDefault(); go(cur()+1); }
    else if(e.key==='ArrowLeft'||e.key==='ArrowUp'||e.key==='PageUp'){ e.preventDefault(); go(cur()-1); }
    else if(e.key==='Home'){ e.preventDefault(); go(0); }
    else if(e.key==='End'){ e.preventDefault(); go(pages.length-1); }
  });
  var overlay=document.getElementById('index');
  if(overlay){
    overlay.addEventListener('click',function(e){
      if(e.target===overlay||e.target.classList.contains('close')) overlay.classList.remove('show');
      if(e.target.tagName==='A') overlay.classList.remove('show');
    });
  }
  document.addEventListener('click',function(e){
    var btn=e.target.closest&&e.target.closest('.copy');
    if(!btn) return;
    var wrap=btn.closest('.codewrap'); if(!wrap) return;
    var pre=wrap.querySelector('pre'); if(!pre) return;
    var text=pre.innerText;
    var done=function(){ var old=btn.textContent; btn.textContent='已复制'; setTimeout(function(){btn.textContent=old;},1600); };
    if(navigator.clipboard&&navigator.clipboard.writeText){ navigator.clipboard.writeText(text).then(done,function(){}); }
    else{ var ta=document.createElement('textarea'); ta.value=text; document.body.appendChild(ta); ta.select();
      try{document.execCommand('copy');done();}catch(err){} document.body.removeChild(ta); }
  });
})();
