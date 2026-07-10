/**
 * Cloudflare Worker — уведомления каталога NeoModern → Telegram (@NeoModern_Bot)
 *
 * Деплой: npx wrangler deploy (см. wrangler.toml)
 * Или вручную: dash.cloudflare.com → Workers → neomodern-notify → Edit code → Deploy
 *
 * Секреты (не в GitHub):
 *   BOT_TOKEN — wrangler secret put BOT_TOKEN
 *   или вставить в редактор Cloudflare при ручном деплое
 */

export default {
  async fetch(request, env) {
    const BOT_TOKEN = env.BOT_TOKEN;
    const CHAT_ID = env.CHAT_ID || '2026940090';
    const API_SECRET = env.API_SECRET || 'neo_7fK2mQx9pL4wR8';
    const CATALOG_URL = env.CATALOG_URL || 'https://ghostvip1717-glitch.github.io/em-c-catalog-bot/';
    const APP_LINK = env.APP_LINK || 'https://t.me/NeoModern_Bot?startapp';

    const cors = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    if (request.method === 'OPTIONS') return new Response(null, { headers: cors });
    if (request.method !== 'POST') return new Response('OK', { headers: cors });

    if (!BOT_TOKEN) {
      return new Response('BOT_TOKEN not configured', { status: 500, headers: cors });
    }

    let data;
    try { data = await request.json(); }
    catch { return new Response('bad json', { status: 400, headers: cors }); }

    if (!data || data.secret !== API_SECRET) {
      return new Response('forbidden', { status: 403, headers: cors });
    }

    let result;
    if (data.type === 'single') result = await sendSingle(data, BOT_TOKEN, CHAT_ID, CATALOG_URL);
    else if (data.type === 'favorites') result = await sendFavorites(data, BOT_TOKEN, CHAT_ID, CATALOG_URL, APP_LINK);
    else return new Response('unknown type', { status: 400, headers: cors });

    return new Response(JSON.stringify(result), {
      status: result.ok ? 200 : 500,
      headers: { ...cors, 'Content-Type': 'application/json' },
    });
  },
};

async function tg(method, token, body) {
  const r = await fetch('https://api.telegram.org/bot' + token + '/' + method, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return r.json();
}

function absPhoto(catalogUrl, url) {
  if (!url) return null;
  if (url.startsWith('http')) return url;
  return catalogUrl + url.replace(/^\//, '');
}

function catalogLink(catalogUrl, id) {
  return catalogUrl + '?m=' + encodeURIComponent(id || '');
}

function senderLine(sender) {
  if (!sender) return '';
  const p = [];
  if (sender.name) p.push(sender.name);
  if (sender.username) p.push('@' + sender.username);
  return p.length ? 'От: ' + p.join(' ') + '\n' : '';
}

async function sendSingle(data, token, chatId, catalogUrl) {
  const m = data.material || {};
  const caption =
    '📋 Запрос по материалу\n' +
    senderLine(data.sender) +
    '\n' + (m.category || '') +
    '\n<b>' + (m.name || '—') + '</b>';
  const photo = absPhoto(catalogUrl, m.image || (m.images && m.images[0]));
  const kb = [[{ text: '🔎 Открыть в каталоге', url: catalogLink(catalogUrl, m.id) }]];

  if (photo) {
    return tg('sendPhoto', token, {
      chat_id: chatId,
      photo,
      caption,
      parse_mode: 'HTML',
      reply_markup: { inline_keyboard: kb },
    });
  }
  return tg('sendMessage', token, {
    chat_id: chatId,
    text: caption + '\n\n' + catalogLink(catalogUrl, m.id),
    parse_mode: 'HTML',
    reply_markup: { inline_keyboard: kb },
  });
}

async function sendFavorites(data, token, chatId, catalogUrl, appLink) {
  const list = data.materials || [];
  if (!list.length) return { ok: false, description: 'empty favorites' };

  let text =
    '⭐ Подборка из избранного (' + list.length + ')\n' +
    senderLine(data.sender) + '\n';

  list.forEach(function(m, i) {
    text += '\n' + (i + 1) + '. ' + (m.category || '') + ' — ' + (m.name || '—');
  });
  text += '\n\nNeoModern · каталог';

  const r1 = await tg('sendMessage', token, {
    chat_id: chatId,
    text,
    reply_markup: {
      inline_keyboard: [[{ text: '📂 Открыть каталог', url: appLink }]],
    },
  });

  if (list.length <= 10) {
    const media = list.map(function(m, i) {
      const photo = absPhoto(catalogUrl, m.image || (m.images && m.images[0]));
      if (!photo) return null;
      return {
        type: 'photo',
        media: photo,
        caption: i === 0 ? 'Фото подборки' : undefined,
      };
    }).filter(Boolean);

    if (media.length) {
      await tg('sendMediaGroup', token, { chat_id: chatId, media });
    }
  }

  return r1;
}
