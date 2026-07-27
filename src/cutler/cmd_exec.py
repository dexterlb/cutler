import asyncio
import os
import re
import shlex

from cutler.errors import JobError

__newline = re.compile(r"[\r\n]")


async def exec_cmd(ctx, name, args, use_out=True):
    args = _override_cmd(ctx.settings.command_override, args)

    if ctx.settings.just_print:
        print(shlex.join(args))
        if use_out:
            raise JobError(
                f"command {os.path.basename(args[0])} will not be run "
                "(just-print) but its output is required"
            )
        return

    async with ctx.cmd_semaphore:
        row = ctx.display.add(name)

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout_chunks = []
        stderr_chunks = []

        def on_line(line):
            return ctx.display.update(row, line)

        try:
            await asyncio.gather(
                _line_by_line(proc.stdout, stdout_chunks, on_line),
                _line_by_line(proc.stderr, stderr_chunks, on_line),
            )
            await proc.wait()
        except asyncio.CancelledError:
            _kill(proc)
            try:
                await proc.wait()
            except asyncio.CancelledError:
                pass
            raise

        stdout = b"".join(stdout_chunks).decode()
        stderr = b"".join(stderr_chunks).decode()

        if proc.returncode != 0:
            ctx.display.failed(row)
            raise JobError(
                "command failed",
                f"failed cmd {name}\ncmd: {shlex.join(args)}\n"
                f"stdout:\n{stdout}\nstderr:\n{stderr}\n",
            )

        ctx.display.done(row)

        if use_out:
            return stdout


def _kill(proc):
    try:
        proc.kill()
    except ProcessLookupError:
        pass


def _override_cmd(command_override, args):
    override = command_override.get(args[0])
    if override is None:
        return args
    prefix = [override] if isinstance(override, str) else list(override)
    return [*prefix, *args[1:]]


async def _line_by_line(reader, chunks, on_line):
    # read
    buf = ""
    while True:
        data = await reader.read(4096)
        if not data:
            break
        chunks.append(data)

        buf += data.decode(errors="replace")
        segments = __newline.split(buf)
        buf = segments.pop()

        last = next((s for s in reversed(segments) if s.strip()), None)
        if buf.strip():
            last = buf
        if last is not None:
            on_line(last.strip())
