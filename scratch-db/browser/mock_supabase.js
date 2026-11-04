(function(){
  const D = window.__DB, calls = (window.__CALLS = []);
  function builder(table){
    const st = {table, single:false};
    const b = {
      select(){return b}, order(){return b}, limit(){return b}, eq(){return b},
      single(){st.single=true;return b}, maybeSingle(){st.single=true;return b},
      then(res,rej){
        const t = D.tables[table];
        let out;
        if (t === undefined || t === null) out = {data:null,error:{message:'relation "'+table+'" does not exist'}};
        else if (t.error) out = {data:null,error:{message:t.error}};
        else out = {data: st.single ? (Array.isArray(t)?t[0]:t) : t, error:null};
        return Promise.resolve(out).then(res,rej);
      }
    };
    return b;
  }
  const client = {
    auth:{
      getSession: async()=>({data:{session:{user:{id:'u1'}}}}),
      signOut: async()=>({}), signInWithPassword: async()=>({error:null})
    },
    from: t=>{(window.__READS=window.__READS||[]).push(t);return builder(t)},
    rpc: async(name,args)=>{
      calls.push({name,args});
      if (D.delay) await new Promise(r=>setTimeout(r,D.delay));
      const h = D.rpc[name];
      if (h === undefined) return {data:null,error:{message:'function '+name+' does not exist'}};
      if (typeof h === 'string') return {data:null,error:{message:h}};
      return {data:h,error:null};
    },
    storage:{from:()=>({createSignedUrl: async()=>({data:{signedUrl:'data:image/gif;base64,R0lGODlhAQABAAAAACw='},error:null})})}
  };
  window.supabase = {createClient: ()=>client};
})();
