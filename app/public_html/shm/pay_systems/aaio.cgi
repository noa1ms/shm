#!/usr/bin/perl

use v5.14;
use Core::Base;
use LWP::UserAgent ();
use Digest::SHA qw(sha1_hex);

use SHM qw(:all);
our %vars = parse_args();
$vars{amount} ||= 100;

if ($vars{action} eq 'create' && $vars{amount}) {
    my $user;
    if ($vars{user_id}) {
        $user = SHM->new(user_id => $vars{user_id});
        unless ($user) {
            print_json({status => 400, msg => 'Error: unknown user'});
            exit 0;
        }

        if ($vars{message_id}) {
            get_service('Transport::Telegram')->deleteMessage(message_id => $vars{message_id});
        }

    } else {
        $user = SHM->new();
    }

    my $config = get_service('config', _id => 'pay_systems');
    unless ($config) {
        print_json({status => 400, msg => 'Error: config pay_systems->aaio not exists'});
        exit 0;
    }

    my $lwp = LWP::UserAgent->new(timeout => 10);
    my $response = $lwp->post(
        'https://api.aaio.dev/payment/create',
        Content_Type => 'application/json',
        Content      => encode_json({
            amount   => $vars{amount},
            order_id => $user->id,
        }),
    );

    if ($response->is_success) {
        my $payment_info = decode_json($response->content);
        my $payment_id   = $payment_info->{id};
        my $redirect_url = "https://api.aaio.dev/payment/$payment_id/redirect";
        
        print_header(
            location => $redirect_url,
            status   => 301,
        );
    } else {
        print_header(status => 503);
        print $response->content;
    }
    exit 0;
}

my $user = SHM->new(skip_check_auth => 1);

my $config = get_service('config', _id => 'pay_systems');
unless ($config) {
    print_json({status => 400, msg => 'Error: config pay_systems->aaio not exists'});
    exit 0;
}

# Здесь можно добавить проверку подлинности уведомления от AAIO,
# если такая функциональность поддерживается AAIO

if ($vars{test_notification}) {
    $user->payment(
        user_id       => 1,
        money         => 0,
        pay_system_id => 'aaio-test',
        comment       => \%vars,
    );
    $user->commit;
    print_json({status => 200, msg => 'Test OK'});
    exit 0;
}

my ($user_id, $amount) = @vars{qw(label withdraw_amount)};

unless ($user_id) {
    print_json({status => 400, msg => 'User (label) required'});
    exit 0;
}

unless ($user = $user->id($user_id)) {
    print_json({status => 404, msg => "User [$user_id] not found"});
    exit 0;
}

unless ($user->lock(timeout => 10)) {
    print_json({status => 408, msg => "The service is locked. Try again later"});
    exit 0;
}

$user->payment(
    user_id       => $user_id,
    money         => $amount,
    pay_system_id => 'aaio',
    comment       => \%vars,
);

$user->commit;

print_json({status => 200, msg => "Payment successful"});

exit 0;
