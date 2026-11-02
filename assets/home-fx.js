/* Home-page motion (the Home view only). Loaded by index.html as assets/home-fx.js?v=1: BUMP THE NUMBER whenever this file changes.
   index.html calls HomeFX.mount() after it draws Home and HomeFX.unmount() on every other screen.
   What lives here (everything else, the drifting discs, the colour flow, the diamond pulse and the button sweep, is CSS in index.html):
     - a short entrance (about 1.2 s) the FIRST time Home is shown in a visit
     - a flash on a date / time / venue row that is tapped (the press ripple on every button is in page-fx.js)
     - a few dim glowing particles in the BACKGROUND (a canvas behind the page content, so they never appear on the cards)
     - DESKTOP ONLY (a real mouse): the card tilts toward the pointer with a light glare, and the logo's two heads look at the pointer
   Nothing here runs for visitors who ask for reduced motion. */
(()=>{
const RM=matchMedia("(prefers-reduced-motion:reduce)"),FINE=matchMedia("(hover:hover) and (pointer:fine)");
const clamp=(x,a=0,b=1)=>Math.min(b,Math.max(a,x)),rnd=(a,b)=>a+Math.random()*(b-a);
const COL0=["#F0A000","#20C8A0","#D82890","#7820E0","#3050F0","#FFC857"];
/* the particle colours come from the page theme (the CSS variable --fx, six #RRGGBB colours); the list above is the fallback */
const cols=()=>{try{const v=getComputedStyle(document.documentElement).getPropertyValue("--fx").split(",").map(x=>x.trim());return v.length===6&&v.every(x=>/^#[0-9a-fA-F]{6}$/.test(x))?v:COL0}catch(_){return COL0}};
const TUNE={particlesPhone:12,particlesDesktop:20,alphaMin:.12,alphaMax:.34,tilt:[6,8]};   /* the numbers worth changing */
let live=null,played=false;
const sprite=c=>{const o=document.createElement("canvas");o.width=o.height=64;const g=o.getContext("2d"),r=g.createRadialGradient(32,32,0,32,32,32);
  r.addColorStop(0,c);r.addColorStop(.35,c+"99");r.addColorStop(1,c+"00");g.fillStyle=r;g.fillRect(0,0,64,64);return o};
function unmount(){if(!live)return;const l=live;live=null;l.stop()}
function mount(){
  unmount();if(RM.matches)return;
  const inv=document.querySelector("#app .invite");if(!inv)return;
  const ac=new AbortController(),on=(t,e,f,o)=>t.addEventListener(e,f,{...o,signal:ac.signal}),timers=[];
  const inner=inv.querySelector(".inner"),pres=inv.querySelector(".pres"),h1=inv.querySelector("h1"),orn=inv.querySelector(".orn"),
        rows=[...inv.querySelectorAll(".when>div")],logo=inv.querySelector("#logo");

  /* ---- 1. entrance: the first time only, finished in about 1.2 s; nothing stays hidden for longer than ~0.5 s ---- */
  if(!played){played=true;
    const A=(n,kf,delay,o={})=>{try{return n.animate(kf,{duration:520,easing:"cubic-bezier(.2,.8,.2,1)",fill:"backwards",delay,...o})}catch(_){}};
    if(pres)A(pres,[{opacity:0,transform:"translateY(10px)"},{opacity:1,transform:"none"}],0);
    if(h1){const txt=h1.textContent;h1.setAttribute("aria-label",txt);h1.textContent="";let i=0;
      txt.split(" ").forEach((w,wi,a)=>{const ws=document.createElement("span");ws.className="fxw";ws.setAttribute("aria-hidden","true");
        [...w].forEach(ch=>{const s=document.createElement("span");s.className="fxl";s.textContent=ch;ws.appendChild(s);
          A(s,[{opacity:0,transform:"translateY(34px) rotate(6deg) scale(.7)"},{opacity:1,transform:"none"}],60+(i++)*38,{duration:650,easing:"cubic-bezier(.2,.9,.3,1.25)"})});
        h1.appendChild(ws);if(wi<a.length-1)h1.appendChild(document.createTextNode(" "))})}
    if(orn){const li=orn.querySelectorAll("i"),b=orn.querySelector("b");
      if(li[0])li[0].style.transformOrigin="100% 50%";if(li[1])li[1].style.transformOrigin="0 50%";
      li.forEach(x=>A(x,[{transform:"scaleX(0)",opacity:0},{transform:"scaleX(1)",opacity:1}],380));
      if(b)A(b,[{transform:"rotate(-135deg) scale(0)"},{transform:"rotate(45deg) scale(1)"}],380)}
    rows.forEach((r,i)=>A(r,[{opacity:0,transform:"translateX(-18px)"},{opacity:1,transform:"none"}],480+i*90,{duration:480}));
    document.querySelectorAll("#app button.big").forEach((b,i)=>A(b,[{opacity:0,transform:"translateY(18px) scale(.96)"},{opacity:1,transform:"none"}],380+i*70));
    const note=document.querySelector("#app .note");if(note)A(note,[{opacity:0},{opacity:1}],800,{duration:400,easing:"ease"});
  }

  /* ---- 2. a flash on a tapped date / time / venue row (the button ripple for ALL buttons lives in page-fx.js) ---- */
  on(document.getElementById("app"),"pointerdown",e=>{
    const t=e.target;if(!t||!t.closest)return;
    const row=t.closest(".when>div");
    if(row){row.classList.add("fxh");timers.push(setTimeout(()=>row.classList.remove("fxh"),600))}
  });

  /* ---- 3. background particles: a fixed canvas BEHIND the page content (main sits above it), so they can never be drawn on a card ---- */
  const cv=document.createElement("canvas");cv.id="fxc";cv.setAttribute("aria-hidden","true");document.body.insertBefore(cv,document.body.firstChild);
  const cx=cv.getContext("2d");let spr=cols().map(sprite),W=0,H=0;on(document,"themechange",()=>{spr=cols().map(sprite)});
  const size=()=>{const dpr=Math.min(devicePixelRatio||1,1.5);W=innerWidth;H=innerHeight;cv.width=W*dpr;cv.height=H*dpr;cx.setTransform(dpr,0,0,dpr,0,0)};size();on(window,"resize",size);
  const N=innerWidth<520?TUNE.particlesPhone:TUNE.particlesDesktop;
  const P=Array.from({length:N},()=>({x:rnd(0,W),y:rnd(0,H),r:rnd(4,12),vy:rnd(-18,-6),ph:rnd(0,6.3),sw:rnd(6,20),sp:rnd(.2,.6),c:Math.random()*6|0,a:rnd(TUNE.alphaMin,TUNE.alphaMax)}));

  /* ---- 4. desktop only: tilt + glare, and the logo's heads follow the pointer ---- */
  const desk=FINE.matches&&inner;let gl=null,px=-999,py=-999,over=false,tx=0,ty=0,gx=0,gy=0,lx=0,ly=0,tilted=false;
  if(desk){gl=document.createElement("div");gl.className="fxg";inv.appendChild(gl);
    on(window,"pointermove",e=>{if(e.pointerType&&e.pointerType!=="mouse")return;px=e.clientX;py=e.clientY;over=true});
    on(document,"mouseleave",()=>{over=false});on(document,"mouseout",e=>{if(!e.relatedTarget)over=false});on(window,"blur",()=>{over=false})}

  let raf=0,last=performance.now(),t=0;
  const tick=now=>{raf=requestAnimationFrame(tick);const dt=Math.min(.033,(now-last)/1000||.016);last=now;t+=dt;
    cx.clearRect(0,0,W,H);cx.globalCompositeOperation="lighter";
    for(const p of P){p.y+=p.vy*dt;p.x+=Math.sin(p.ph+t*p.sp)*p.sw*dt;
      if(p.y<-30){p.y=H+30;p.x=rnd(0,W)}if(p.x<-30)p.x=W+30;else if(p.x>W+30)p.x=-30;
      cx.globalAlpha=p.a*(.75+.25*Math.sin(t*p.sp*3+p.ph));cx.drawImage(spr[p.c],p.x-p.r,p.y-p.r,p.r*2,p.r*2)}
    cx.globalAlpha=1;
    if(desk){
      const ir=inv.getBoundingClientRect(),inside=over&&px>ir.left-20&&px<ir.right+20&&py>ir.top-20&&py<ir.bottom+20,k=1-Math.exp(-dt*9);
      const ttx=inside?clamp((py-(ir.top+ir.height/2))/ir.height,-.5,.5)*-TUNE.tilt[0]:0,tty=inside?clamp((px-(ir.left+ir.width/2))/ir.width,-.5,.5)*TUNE.tilt[1]:0;
      tx+=(ttx-tx)*k;ty+=(tty-ty)*k;
      if(Math.abs(tx)>.01||Math.abs(ty)>.01||Math.abs(ttx)>0||Math.abs(tty)>0){inner.style.transform=`perspective(900px) rotateX(${tx.toFixed(2)}deg) rotateY(${ty.toFixed(2)}deg)`;tilted=true}
      else if(tilted){inner.style.transform="";tilted=false}
      if(inside){inv.style.setProperty("--gx",(px-ir.left)+"px");inv.style.setProperty("--gy",(py-ir.top)+"px");inv.style.setProperty("--go",.8)}else inv.style.setProperty("--go",0);
      if(logo&&window.LogoFluid&&LogoFluid.look){const r=logo.getBoundingClientRect(),tlx=over?clamp((px-(r.left+r.width/2))/260,-1,1)*5:0,tly=over?clamp((py-(r.top+r.height/2))/260,-1,1)*3.5:0;
        lx+=(tlx-lx)*k;ly+=(tly-ly)*k;if(Math.abs(lx-gx)>.005||Math.abs(ly-gy)>.005){gx=lx;gy=ly;LogoFluid.look(lx,ly)}}
    }};
  raf=requestAnimationFrame(tick);
  live={n:N,stop(){cancelAnimationFrame(raf);ac.abort();timers.forEach(clearTimeout);cv.remove();if(gl)gl.remove();
    if(inner)inner.style.transform="";inv.style.removeProperty("--go");
    try{if(window.LogoFluid&&LogoFluid.look)LogoFluid.look(0,0)}catch(_){}}};
}
window.HomeFX={mount,unmount,info:()=>({mounted:!!live,particles:live?live.n:0,canvases:document.querySelectorAll("#fxc").length})};
})();
