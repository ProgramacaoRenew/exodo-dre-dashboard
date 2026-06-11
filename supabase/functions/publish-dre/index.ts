// ============================================================
// Edge Function: publish-dre
// Recebe o JSON da DRE do publicador e grava no banco usando a
// service_role (que fica SÓ no servidor, nunca no .exe/frontend).
//
// Deploy:
//   supabase functions deploy publish-dre --no-verify-jwt
//   supabase secrets set PUBLISH_SECRET="um-segredo-forte-aqui"
// (SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY são injetadas automaticamente.)
// ============================================================
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return new Response("method not allowed", { status: 405 });
  }

  // Autenticação do publicador via segredo compartilhado.
  if (req.headers.get("x-publish-secret") !== Deno.env.get("PUBLISH_SECRET")) {
    return new Response("unauthorized", { status: 401 });
  }

  let body: { data?: unknown; rev?: string };
  try {
    body = await req.json();
  } catch {
    return new Response("invalid json", { status: 400 });
  }

  if (!Array.isArray(body.data) || typeof body.rev !== "string") {
    return new Response("bad payload", { status: 400 });
  }

  const sb = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  );

  const { error } = await sb.from("dre_snapshot").upsert({
    id: 1,
    data: body.data,
    rev: body.rev,
    updated_at: new Date().toISOString(),
  });

  if (error) return new Response(error.message, { status: 500 });
  return new Response(JSON.stringify({ ok: true }), {
    headers: { "Content-Type": "application/json" },
  });
});
