/* Ehsaas'26 Home motion (the Home view only). Loaded by index.html as assets/home-fx.js?v=3: BUMP THE NUMBER whenever this file changes.
   index.html calls HomeFX.mount() right after it draws Home and HomeFX.unmount() on every other screen.
   The matching CSS is the second <style> block in index.html (everything in it is scoped to html.fx, which index.html adds only when the
   visitor has NOT asked for reduced motion). The numbers worth changing are in TUNE.

   What this script does (it only looks and moves; every click is handled by index.html):
     - splits the title into letters and the story paragraph into words (the story words light up as you scroll down the page)
     - the thin progress line in the header, the scroll cue, the header gaining depth on scroll
     - the poster: tilt + glare with a mouse, and lightbox() (the poster grows out of itself when tapped)
     - the two countdowns (registration, and the meetup). They read three attributes of the .home element, which index.html keeps up to date:
         data-event  start of the meetup (ISO time)
         data-close  registration deadline (ISO time), empty = hide the registration countdown
         data-skew   milliseconds to add to this phone's clock to get server time
     - scroll reveal with staggers, the floating button showing after the hero, the "Only N spots left" count-down
     - glowing dots behind the hero heading, the logo's heads and the discs following a mouse pointer, a warm light on the cards
     - a press ripple on the date and venue cards (buttons get theirs from page-fx.js, so they are NOT done here: Home would get two)
     - one short confetti burst when the main Register button is pressed
   Nothing here runs for visitors who ask for reduced motion, except what is needed to show every block and run the countdowns. */
(()=>{
const RM=matchMedia("(prefers-reduced-motion:reduce)").matches,FINE=matchMedia("(hover:hover) and (pointer:fine)").matches;
const TUNE={particlesPhone:14,particlesDesktop:26,parallax:.18,parallaxMax:60,poster:{tilt:7}};
const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
const clamp=(x,a=0,b=1)=>Math.min(b,Math.max(a,x)),rnd=(a,b)=>a+Math.random()*(b-a);
const COL=["#FFA300","#FFC24D","#8FA8FF","#3050F0","#20C8A0","#D82890"];
let live=null,played=false;

/* ---------- small helpers ---------- */
function splitChars(el){const label=el.getAttribute("aria-label")||el.textContent;el.setAttribute("aria-label",label);let i=0;
  const walk=n=>[...n.childNodes].forEach(c=>{
    if(c.nodeType===3){const f=document.createDocumentFragment();[...c.textContent].forEach(ch=>{const s=document.createElement("span");s.className="fxc";s.setAttribute("aria-hidden","true");s.style.setProperty("--i",i++);s.textContent=ch;f.appendChild(s)});c.replaceWith(f)}
    else if(c.nodeType===1)walk(c)});
  walk(el);return i}
function splitWords(el,cls){let i=0;
  const walk=n=>[...n.childNodes].forEach(c=>{
    if(c.nodeType===3){const f=document.createDocumentFragment();
      c.textContent.split(/(\s+)/).forEach(t=>{if(!t)return;if(/^\s+$/.test(t))f.appendChild(document.createTextNode(t));
        else{const s=document.createElement("span");s.className=cls;s.style.setProperty("--i",i++);s.textContent=t;f.appendChild(s)}});c.replaceWith(f)}
    else if(c.nodeType===1)walk(c)});
  walk(el);return i}
const sprite=c=>{const o=document.createElement("canvas");o.width=o.height=64;const g=o.getContext("2d"),r=g.createRadialGradient(32,32,0,32,32,32);
  r.addColorStop(0,c);r.addColorStop(.4,c+"88");r.addColorStop(1,c+"00");g.fillStyle=r;g.fillRect(0,0,64,64);return o};

/* ---------- confetti burst from a point (one short burst, then the canvas is removed) ---------- */
function confetti(x,y){
  if(RM)return;const cv=document.createElement("canvas");cv.className="fxconf";cv.setAttribute("aria-hidden","true");const dpr=Math.min(devicePixelRatio||1,1.5);
  const W=innerWidth,H=innerHeight;cv.width=W*dpr;cv.height=H*dpr;document.body.appendChild(cv);const g=cv.getContext("2d");g.scale(dpr,dpr);
  const cols=["#FFA300","#FFC24D","#D82890","#7820E0","#20C8A0","#3050F0","#E86818","#FFFFFF"];
  const ps=Array.from({length:innerWidth<520?60:90},()=>{const a=rnd(-Math.PI*.95,-Math.PI*.05),v=rnd(280,760);
    return{x,y,vx:Math.cos(a)*v,vy:Math.sin(a)*v,w:rnd(6,11),h:rnd(4,8),r:rnd(0,6.3),vr:rnd(-12,12),c:cols[Math.random()*cols.length|0],round:Math.random()<.3}});
  const t0=performance.now();let last=t0;
  (function f(now){const dt=Math.min(.033,(now-last)/1000);last=now;const age=(now-t0)/1000;g.clearRect(0,0,W,H);
    for(const p of ps){p.vy+=900*dt;p.vx*=1-1.4*dt;p.x+=p.vx*dt;p.y+=p.vy*dt;p.r+=p.vr*dt;
      g.globalAlpha=clamp(1-(age-1.1)/.8);g.fillStyle=p.c;g.save();g.translate(p.x,p.y);g.rotate(p.r);
      if(p.round){g.beginPath();g.arc(0,0,p.w/2,0,6.3);g.fill()}else g.fillRect(-p.w/2,-p.h/2,p.w,p.h);g.restore()}
    if(age<1.9)requestAnimationFrame(f);else cv.remove()})(t0);
}

/* ---------- image lightbox: grows out of the picture and shrinks back into it ---------- */
function lightbox(img){
  const from=img.getBoundingClientRect(),d=document.createElement("div");d.className="hlb";d.innerHTML='<img alt="">';const big=d.firstChild;big.src=img.currentSrc||img.src;
  document.body.appendChild(d);requestAnimationFrame(()=>d.classList.add("on"));
  const run=(rev)=>{const to=big.getBoundingClientRect();if(!to.width)return;
    const kf={transform:`translate(${from.left+from.width/2-(to.left+to.width/2)}px,${from.top+from.height/2-(to.top+to.height/2)}px) scale(${from.width/to.width})`};
    try{return big.animate(rev?[{transform:"none"},kf]:[kf,{transform:"none"}],{duration:rev?320:520,easing:"cubic-bezier(.16,1,.3,1)",fill:"both"})}catch(_){}};
  if(big.complete)run(false);else big.onload=()=>run(false);
  let closing=false;const key=e=>{if(e.key==="Escape")d.onclick()};addEventListener("keydown",key);
  d.onclick=()=>{if(closing)return;closing=true;removeEventListener("keydown",key);d.classList.remove("on");const a=run(true);setTimeout(()=>d.remove(),a?330:0)};
}

/* ---------- mount ---------- */
function mount(){
  unmount();const root=$("#app .home");if(!root)return;
  const ac=new AbortController(),on=(t,e,f,o)=>t&&t.addEventListener(e,f,{...o,signal:ac.signal}),timers=[],cleanups=[];
  const hero=$(".hhero",root),head=$(".hhead",root),photo=$(".hhero-photo",root),fab=$("#home-fab",root),join=$("#home-join",root);
  if(!hero)return;   /* the home page has no top bar any more, so the header is optional here */
  played=true;
  let cv=null,tickNow=null;

  /* the title and the story words are split into pieces BEFORE anything is shown */
  const h1=$("h1",hero);if(h1&&!RM&&!h1.dataset.fx){h1.dataset.fx=1;splitChars(h1)}
  const lede=$(".hlede",hero);if(lede&&!RM&&!lede.dataset.fx){lede.dataset.fx=1;splitWords(lede,"fxlw")}
  const sp=$("#story p",root);let words=[];if(sp){if(!sp.dataset.fx){sp.dataset.fx=1;splitWords(sp,"fxsw")}words=$$(".fxsw",sp)}

  /* the progress line in the header */
  const prog=document.createElement("i");prog.className="fxprog";prog.setAttribute("aria-hidden","true");if(head)head.appendChild(prog);

  /* the scroll cue */
  const cue=document.createElement("div");cue.className="fxcue";cue.setAttribute("aria-hidden","true");hero.appendChild(cue);

  /* the poster gets a wrapper (so tilting never fights the reveal) and a glare layer */
  const img=$("#home-poster",root),fig=img&&img.closest(".hposter");let tilt=null,glare=null;
  if(fig&&!fig.parentNode.classList.contains("fxtilt")){tilt=document.createElement("div");tilt.className="fxtilt";fig.parentNode.insertBefore(tilt,fig);tilt.appendChild(fig);
    glare=document.createElement("div");glare.className="fxglare";fig.appendChild(glare)}

  /* footer takes part in the reveal */
  const foot=$(".hfoot",root);

  /* ---- countdowns: small "registration" pill on top, big "meetup" countdown under it (markup is drawn by index.html) ---- */
  const cd=$(".fxbig",root),reg=$(".fxreg",root),cap=$(".fxcdcap",root);
  if(cd&&reg&&cap){
    const rl=$(".fxrl",reg),rn=$$("b",reg),rp=[],nodes=$$("b",cd),bars=$$("i",cd),cells=$$(":scope>div",cd),prev=[];
    const now=()=>Date.now()+(+root.dataset.skew||0);
    const roll=el=>{if(RM)return;try{el.animate([{transform:"translateY(-60%) scale(.8)",opacity:0,filter:"blur(6px)"},{transform:"none",opacity:1,filter:"none"}],{duration:520,easing:"cubic-bezier(.16,1,.3,1)"})}catch(_){}};
    const tick=()=>{
      const ev=new Date(root.dataset.event).getTime();
      if(!isNaN(ev)){
        const s=Math.max(0,Math.floor((ev-now())/1000)),v=[Math.floor(s/86400),Math.floor(s%86400/3600),Math.floor(s%3600/60),s%60],frac=[Math.min(1,v[0]/60),v[1]/24,v[2]/60,v[3]/60];
        v.forEach((n,i)=>{const t=String(n).padStart(2,"0");
          bars[i].style.setProperty("--p",i===3&&n===0?0:frac[i]);
          if(nodes[i].textContent!==t){nodes[i].textContent=t;
            if(prev[i]!==undefined){roll(nodes[i]);if(!RM){cells[i].classList.remove("fxflash");void cells[i].offsetWidth;cells[i].classList.add("fxflash")}}
            prev[i]=n}});
        cap.textContent=s===0?"It's happening now!":"Countdown to the meetup"}
      /* registration: shown only while the page knows a deadline */
      const close=root.dataset.close?new Date(root.dataset.close).getTime():NaN;
      if(isNaN(close)){reg.hidden=true;return}
      reg.hidden=false;
      const left=Math.floor((close-now())/1000),r=Math.max(0,left);
      if(left<=0){rl.textContent="Registration closed";reg.classList.add("fxclosed")}else{rl.textContent="Registration open for:";reg.classList.remove("fxclosed")}
      [Math.floor(r/86400),Math.floor(r%86400/3600),Math.floor(r%3600/60),r%60].forEach((n,i)=>{const t=String(n).padStart(2,"0");
        if(rn[i].textContent!==t){rn[i].textContent=t;if(rp[i]!==undefined&&!RM)try{rn[i].animate([{transform:"translateY(-60%)",opacity:0},{transform:"none",opacity:1}],{duration:380,easing:"cubic-bezier(.16,1,.3,1)"})}catch(_){}rp[i]=n}});
    };
    tickNow=tick;tick();const id=setInterval(()=>{if(!document.hidden)tick()},1000);cleanups.push(()=>clearInterval(id));
  }

  /* ---- scroll reveal with staggers ---- */
  const rv=$$(".rv",root);if(foot)rv.push(foot);
  $$(".hgrid,.fxstub",root).forEach(g=>$$(".hc",g).forEach((el,i)=>el.style.setProperty("--d",(i*110)+"ms")));
  if(cd)cd.style.setProperty("--d","60ms");
  const settle=el=>timers.push(setTimeout(()=>el.classList.add("rd"),1700));
  if(RM||!("IntersectionObserver" in window)){rv.forEach(e=>e.classList.add("in"));words.forEach(w=>w.classList.add("lit"))}
  else{const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add("in");io.unobserve(e.target);settle(e.target)}}),{threshold:.12,rootMargin:"0px 0px -6% 0px"});
    rv.forEach(e=>io.observe(e));cleanups.push(()=>io.disconnect())}

  /* ---- floating button: shows after the hero, hides while the join card is on screen ---- */
  let joinSeen=false;
  if(join&&"IntersectionObserver" in window){const io2=new IntersectionObserver(es=>es.forEach(e=>{joinSeen=e.isIntersecting;frame()}),{threshold:.35});io2.observe(join);cleanups.push(()=>io2.disconnect())}

  /* ---- one scroll handler for everything scroll-linked (header, progress, parallax, story words, floating button) ---- */
  let ticking=false,litN=0;
  function frame(){ticking=false;const y=scrollY,max=document.documentElement.scrollHeight-innerHeight,vh=innerHeight;
    prog.style.transform=`scaleX(${max>0?clamp(y/max):0})`;
    if(head)head.classList.toggle("sc",y>24);
    if(!RM&&photo&&y<hero.offsetHeight+120)photo.style.translate=`0 ${Math.min(y*TUNE.parallax,TUNE.parallaxMax)}px`;
    if(y>40)cue.classList.add("gone");
    if(words.length&&!RM){const r=sp.getBoundingClientRect(),p=clamp((vh*.9-r.top)/(r.height+vh*.4)),n=Math.round(p*words.length);
      if(n!==litN){const a=Math.min(n,litN),b=Math.max(n,litN);for(let i=a;i<b;i++)words[i].classList.toggle("lit",i<n);litN=n}}
    if(fab)fab.classList.toggle("show",y>hero.offsetHeight*.75&&!joinSeen)}
  const onScroll=()=>{if(!ticking){ticking=true;requestAnimationFrame(frame)}};
  on(window,"scroll",onScroll,{passive:true});on(window,"resize",onScroll);frame();

  /* ---- shared by both modes ---- */
  const finish=()=>{
    spots();
    /* press ripple on the date and venue cards (buttons get theirs from page-fx.js) */
    on(root,"pointerdown",e=>{if(RM)return;if(e.pointerType==="touch")return;   /* a finger landing on the card is usually the start of a scroll, not a tap */
      const b=e.target.closest&&e.target.closest("a.hc");if(!b)return;
      const r=b.getBoundingClientRect(),d=Math.max(r.width,r.height)*2.2,s=document.createElement("span");s.className="fxr";s.setAttribute("aria-hidden","true");
      s.style.cssText=`width:${d}px;height:${d}px;left:${e.clientX-r.left-d/2}px;top:${e.clientY-r.top-d/2}px;z-index:2`;b.appendChild(s);
      try{s.animate([{transform:"scale(0)",opacity:.5},{transform:"scale(1)",opacity:0}],{duration:650,easing:"ease-out"}).onfinish=()=>s.remove()}catch(_){s.remove()}setTimeout(()=>s.remove(),900)},{passive:true});
    /* confetti from the main Register button (a returning visitor's main button opens their ticket instead, so no confetti there) */
    const conf=e=>{if(RM||root.classList.contains("ret"))return;const r=e.currentTarget.getBoundingClientRect();confetti(r.left+r.width/2,r.top+r.height/2)};
    on($("#go-register",root),"click",conf);on($("#hero-register",root),"click",conf);
  };

  /* the "Only N spots left" numbers count down once, when they first scroll into view; later changes just replace the number */
  function spots(){$$(".fxspots b[data-to]",root).forEach(b=>{
    const to=+b.dataset.to;if(!(to>=0)||b._to===to)return;
    const first=b._to===undefined;b._to=to;
    if(!first||RM||!("IntersectionObserver" in window)){b.textContent=to;return}
    const delay=+b.dataset.delay||0;b.textContent=to+22;
    const io=new IntersectionObserver(es=>{if(!es[0].isIntersecting)return;io.disconnect();
      timers.push(setTimeout(()=>{const f0=to+22,t0=performance.now();(function f(n){const end=+b.dataset.to,k=clamp((n-t0)/1200);b.textContent=Math.round(f0+(end-f0)*(1-Math.pow(1-k,3)));if(k<1)requestAnimationFrame(f)})(t0)},delay))},{threshold:.6});
    io.observe(b);cleanups.push(()=>io.disconnect())})}

  if(RM){finish();live={n:0,stop,refresh};return}

  /* ---- hero: glowing dots drifting up behind the heading (paused when the hero is off screen) ---- */
  cv=document.createElement("canvas");cv.className="fxcanvas";cv.setAttribute("aria-hidden","true");hero.insertBefore(cv,$(".hw",hero));
  const cx=cv.getContext("2d"),spr=COL.map(sprite);let W=0,H=0;
  const size=()=>{const dpr=Math.min(devicePixelRatio||1,1.5);W=hero.clientWidth;H=hero.clientHeight;cv.width=W*dpr;cv.height=H*dpr;cx.setTransform(dpr,0,0,dpr,0,0)};size();on(window,"resize",size);
  const N=innerWidth<520?TUNE.particlesPhone:TUNE.particlesDesktop;
  const P=Array.from({length:N},()=>({x:rnd(0,W),y:rnd(0,H),r:rnd(5,15),vy:rnd(-22,-8),ph:rnd(0,6.3),sw:rnd(8,26),sp:rnd(.25,.7),c:Math.random()*COL.length|0,a:rnd(.16,.42)}));
  let heroVis=true,raf=0,last=performance.now(),t=0;
  if("IntersectionObserver" in window){const io3=new IntersectionObserver(es=>es.forEach(e=>{heroVis=e.isIntersecting}));io3.observe(hero);cleanups.push(()=>io3.disconnect())}

  /* ---- desktop pointer: the soft discs and the logo's heads follow the pointer, the poster tilts ---- */
  let px=0,py=0,tpx=0,tpy=0,over=false,lg=[0,0],tl=[0,0];
  if(FINE){
    on(hero,"pointermove",e=>{if(e.pointerType&&e.pointerType!=="mouse")return;const r=hero.getBoundingClientRect();tpx=clamp((e.clientX-r.left)/r.width*2-1,-1,1);tpy=clamp((e.clientY-r.top)/r.height*2-1,-1,1);over=true;
      hero.style.setProperty("--px",tpx.toFixed(3));hero.style.setProperty("--py",tpy.toFixed(3))});
    on(hero,"pointerleave",()=>{over=false;tpx=tpy=0;hero.style.setProperty("--px",0);hero.style.setProperty("--py",0)});
    if(tilt){const lim=TUNE.poster.tilt;
      on(tilt,"pointermove",e=>{if(e.pointerType&&e.pointerType!=="mouse")return;const r=fig.getBoundingClientRect(),x=clamp((e.clientX-r.left)/r.width),y=clamp((e.clientY-r.top)/r.height);
        fig.style.transform=`rotateX(${((.5-y)*lim*2).toFixed(2)}deg) rotateY(${((x-.5)*lim*2).toFixed(2)}deg) scale(1.025)`;
        fig.style.setProperty("--gx",x*100+"%");fig.style.setProperty("--gy",y*100+"%");fig.style.setProperty("--go",1)});
      on(tilt,"pointerleave",()=>{fig.style.transform="";fig.style.setProperty("--go",0)})}
  }
  const loop=now=>{raf=requestAnimationFrame(loop);const dt=Math.min(.033,(now-last)/1000||.016);last=now;if(document.hidden)return;
    if(heroVis){t+=dt;cx.clearRect(0,0,W,H);cx.globalCompositeOperation="lighter";
      for(const p of P){p.y+=p.vy*dt;p.x+=Math.sin(p.ph+t*p.sp)*p.sw*dt;if(p.y<-30){p.y=H+30;p.x=rnd(0,W)}
        cx.globalAlpha=p.a*(.7+.3*Math.sin(t*p.sp*3+p.ph));cx.drawImage(spr[p.c],p.x-p.r,p.y-p.r,p.r*2,p.r*2)}
      cx.globalAlpha=1;
      if(FINE&&window.LogoFluid&&LogoFluid.look){const k=1-Math.exp(-dt*8);tl=[over?tpx*5:0,over?tpy*3.5:0];lg=[lg[0]+(tl[0]-lg[0])*k,lg[1]+(tl[1]-lg[1])*k];
        if(Math.abs(lg[0]-px)>.004||Math.abs(lg[1]-py)>.004){px=lg[0];py=lg[1];LogoFluid.look(px,py)}}}};
  raf=requestAnimationFrame(loop);cleanups.push(()=>{cancelAnimationFrame(raf);try{if(window.LogoFluid&&LogoFluid.look)LogoFluid.look(0,0)}catch(_){}});

  /* ---- cards: a warm light follows the pointer (or the tap on a phone) ---- */
  $$(".hgrid .hc",root).forEach(c=>{
    const set=e=>{const r=c.getBoundingClientRect();c.style.setProperty("--mx",(e.clientX-r.left)+"px");c.style.setProperty("--my",(e.clientY-r.top)+"px")};
    on(c,"pointermove",e=>{if(e.pointerType==="mouse"){set(e);c.style.setProperty("--so",1)}});
    on(c,"pointerleave",()=>c.style.setProperty("--so",0));
    on(c,"pointerdown",e=>{if(e.pointerType!=="mouse"){set(e);c.style.setProperty("--so",1);timers.push(setTimeout(()=>c.style.setProperty("--so",0),550))}});
  });

  finish();
  live={n:N,stop,refresh};

  function stop(){ac.abort();timers.forEach(clearTimeout);cleanups.forEach(f=>{try{f()}catch(_){}});prog.remove();cue.remove();if(cv)cv.remove()}
  function refresh(){spots();if(tickNow)tickNow()}
}
function unmount(){if(live){const l=live;live=null;l.stop()}}
window.HomeFX={mount,unmount,lightbox,
  refresh:()=>{if(live)live.refresh()},                        /* index.html calls this after it changes the numbers on Home */
  seen:()=>played,                                            /* true once Home has been shown in this visit (the long entrance then plays only the first time) */
  info:()=>({mounted:!!live,particles:live?live.n:0,canvases:document.querySelectorAll("canvas.fxcanvas").length})};
})();
