create table if not exists public.users (
    id bigserial primary key,
    display_name text not null,
    email text not null unique,
    password_hash text not null,
    password_salt text not null,
    created_at timestamptz not null default now()
);

create table if not exists public.app_sessions (
    token text primary key,
    user_id bigint not null references public.users(id) on delete cascade,
    created_at timestamptz not null default now()
);

create table if not exists public.posts (
    id bigserial primary key,
    user_id bigint not null references public.users(id) on delete cascade,
    dish text not null,
    note text not null default '',
    photo_path text,
    photo_public_url text,
    category text not null,
    created_at timestamptz not null default now()
);

create index if not exists posts_user_id_idx on public.posts(user_id);
create index if not exists posts_created_at_idx on public.posts(created_at desc);
create index if not exists posts_category_idx on public.posts(category);
